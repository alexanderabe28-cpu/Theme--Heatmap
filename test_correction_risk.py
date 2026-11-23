"""Logiktests ohne Netz. Aufruf: pytest -q test_correction_risk.py"""
import numpy as np
import pandas as pd

import correction_risk as cr


def _synthetic(n=900, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-01", periods=n)
    data = {}
    for t in cr.TICKERS:
        steps = rng.normal(0.0003, 0.01, n)
        data[t] = 100 * np.exp(np.cumsum(steps))
    return pd.DataFrame(data, index=idx)


def test_no_lookahead():
    px = _synthetic()
    full = cr.compute_levels(px)
    cut = 700
    part = cr.compute_levels(px.iloc[:cut])
    cols = ["gate", "C", "B", "R", "V", "level"]
    a = full.iloc[:cut][cols].astype(float)
    b = part[cols].astype(float)
    pd.testing.assert_frame_equal(a, b)


def test_level_is_zero_outside_gate():
    px = _synthetic()
    d = cr.compute_levels(px)
    d = d[d["valid"]]
    assert (d.loc[d["gate"] == False, "level"] == 0).all()  # noqa: E712
    inside = d[d["gate"] == True]  # noqa: E712
    assert (inside["level"] == inside["n_conf"]).all()
    assert d["level"].between(0, 4).all()


def test_gate_definition():
    px = _synthetic()
    d = cr.compute_levels(px)
    t = d.index[600]
    hi = px["SPY"].iloc[600 - 251:601].max()
    assert bool(d.loc[t, "gate"]) == bool(px["SPY"].iloc[600] >= 0.97 * hi)


def test_component_credit_by_hand():
    px = _synthetic()
    d = cr.compute_levels(px)
    i = 500
    x = px["HYG"] / px["IEF"]
    expect = (x.iloc[i] < x.iloc[i - 49:i + 1].mean()) and (x.iloc[i] / x.iloc[i - 20] < 1)
    assert bool(d["C"].iloc[i]) == bool(expect)


def test_outcomes_and_censoring():
    idx = pd.bdate_range("2020-01-01", periods=60)
    spy = np.full(60, 100.0)
    spy[10] = 94.0          # Tag 10: -6 % gegen Tage davor
    df = pd.DataFrame({"spy": spy}, index=idx)
    o = cr.add_outcomes(df)
    assert o["y45"].iloc[0] == 1.0          # Fenster t+1..t+45 enthaelt Tag 10
    assert o["y45"].iloc[9] == 1.0
    assert o["y45"].iloc[10] == 0.0         # danach +6 %, kein Treffer, Fenster voll
    assert o["y45"].iloc[14] == 0.0         # letztes volles Fenster (14+45=59)
    assert np.isnan(o["y45"].iloc[15])      # unvollstaendig und kein Treffer
    assert np.isnan(o["y45"].iloc[-1])


def test_censored_hit_counts():
    idx = pd.bdate_range("2020-01-01", periods=30)
    spy = np.full(30, 100.0)
    spy[-1] = 90.0
    o = cr.add_outcomes(pd.DataFrame({"spy": spy}, index=idx))
    assert o["y45"].iloc[-2] == 1.0         # Fenster unvollstaendig, Treffer schon da


def test_episode_starts():
    lvl = pd.Series([0] * 25 + [2, 2, 3, 0, 2] + [0] * 25 + [2])
    s2 = cr.episode_starts(lvl, 2, gap=20)
    assert list(np.where(s2)[0]) == [25, 55]   # Index 29 liegt innerhalb der 20 Sessions
    s3 = cr.episode_starts(lvl, 3, gap=20)
    assert list(np.where(s3)[0]) == [27]


def test_level_markers_are_the_first_signals():
    lvl = pd.Series([0] * 25 + [2, 2, 3, 0, 2] + [0] * 25 + [2])
    m = cr.level_markers(lvl, gap=20)
    assert list(m.index) == [25, 27, 55] and list(m) == [2, 3, 2]
    d = cr.compute_levels(_synthetic())
    level = d[d["valid"]]["level"]
    m = cr.level_markers(level)
    starts = pd.concat([cr.episode_starts(level, k) for k in (1, 2, 3, 4)], axis=1)
    assert set(m.index) == set(level.index[starts.any(axis=1)])   # Marker = Tage mit mindestens einem Episodenstart
    assert (m == level.loc[m.index]).all()
    for t, k in m.items():                                         # Zahl am Marker = hoechste Schwelle, die an dem Tag startet
        assert max(j for j in (1, 2, 3, 4) if starts.loc[t].iloc[j - 1]) == k == level.loc[t]


def test_sessions_since_warn():
    lvl = pd.Series([0, 1, 3, 0, 0, 4, 2, 0])
    s = cr.sessions_since_warn(lvl)
    assert s.iloc[:2].isna().all()                       # vor dem ersten Warntag kein Fenster
    assert list(s.iloc[2:]) == [0, 1, 2, 0, 1, 2]        # zaehlt ab dem letzten Tag mit Level >= 3
    d = cr.compute_levels(_synthetic())
    level = d[d["valid"]]["level"]
    since = cr.sessions_since_warn(level)
    warn_pos = np.where(level.to_numpy() >= cr.WARN_LEVEL)[0]
    for i in (len(level) - 1, len(level) // 2):
        prior = warn_pos[warn_pos <= i]
        assert (np.isnan(since.iloc[i]) and len(prior) == 0) or since.iloc[i] == i - prior[-1]


def test_bh():
    res = cr._bh({2: 0.01, 3: 0.04, 4: 0.5}, q=0.10)
    assert res == {2: True, 3: True, 4: False}


def test_backtest_constants_consistent():
    bt = cr.BACKTEST
    for s in bt["samples"]:
        assert sum(s["tage"]) == s["gate_tage"]
        assert s["ab3"]["tage"] == s["tage"][3] + s["tage"][4]
        hits = sum(q * t for q, t in zip(s["quote"], s["tage"]))
        assert abs(hits / s["gate_tage"] - s["basis"]) < 0.002
    assert bt["gesamt"]["gate_tage"] == sum(s["gate_tage"] for s in bt["samples"])
    assert set(cr.COMPONENTS) <= set(bt["komponenten"])


def test_forward_track_only_after_freeze_and_warn_state():
    px = _synthetic(n=1200, seed=3)
    df = cr.add_outcomes(cr.compute_levels(px))
    since = str(px.index[600].date())
    t = cr.forward_track(df, since=since)
    assert (t.index > pd.Timestamp(since)).all()
    assert (t["level"] >= cr.WARN_LEVEL).all()
    expect = df[df["valid"] & (df.index > pd.Timestamp(since)) & (df["gate"] == True) & (df["level"] >= 3)]  # noqa: E712
    assert len(t) == len(expect)
    s = cr.forward_summary(t)
    assert s["tage"] == s["bekannt"] + s["offen"] and s["treffer"] <= s["bekannt"]
