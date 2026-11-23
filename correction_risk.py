"""Correction-Risk-Modell (Eigenbau), Spec v1.1 vom 22.11.2026.

Struktur nach dem Vorbild des TSF Correction Risk Model: Gate nahe Hoch,
Bestaetigungen aus anderen Maerkten (Credit, Breadth, Rotation, Volatility),
Level 0-4. Die Signale sind seit v1.0 unveraendert. v1.1 liest das Level als
Zustand (jeder Tag, an dem es anliegt) statt als Erstsignal und traegt die
Ergebnisse des Volltests (BACKTEST) mit. Status: nicht belegt, Schattenmodus.
Regeln und Tests: SPEC_correction_risk.md (v1.0), PROTOKOLL_v1.1.md, SPEC_v1.1.md.

Dieses Modul ist frei von Streamlit und laesst sich in jede App einhaengen.
Kein Lookahead: Level[t] nutzt nur Schlusskurse bis einschliesslich t.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SPEC_VERSION = "1.1"
FREEZE_DATE = "2026-11-20"   # letzter Datentag der Tests; alles danach ist Live-Out-of-Sample
WARN_LEVEL = 3               # Warnzustand ab 3 von 4 Bestaetigungen
TICKERS = ["SPY", "RSP", "HYG", "IEF", "XLY", "XLP", "^VIX"]
# Abstufung mit den Namen der TSF-Blaetter. Nur Benennung: Die Zahlen je Level stehen in BACKTEST,
# dort liegt Level 1 an der Basis und Level 4 nicht ueber Level 3.
LEVEL_NAMES = {0: "unauffällig", 1: "ELEVATED", 2: "HIGH", 3: "VERY HIGH", 4: "EXTREME"}
COMPONENTS = {
    "C": "Credit (HYG/IEF)",
    "B": "Breadth (RSP)",
    "R": "Rotation (XLY/XLP)",
    "V": "Volatility (VIX)",
}

# Eingefrorene Ergebnisse des Volltests (Lauf vom 22.11.2026, siehe SPEC_v1.1.md).
# "quote" = Anteil der Gate-Tage mit diesem Level, denen binnen 45 Sessions ein Schluss
# >= 5 % unter dem Tagesschluss folgte. Index der Listen = Level 0..4.
# "komponenten": Lift und Shift-p je Stichprobe; S, F, D wurden getestet und verworfen.
BACKTEST = {'samples': [{'key': 'H2',
              'label': '1999–2007',
              'rolle': 'blinder Test, Proxys',
              'gate_tage': 894,
              'basis': 0.215884,
              'tage': [490, 254, 112, 32, 6],
              'treffer': [99, 54, 37, 2, 1],
              'quote': [0.202041, 0.212598, 0.330357, 0.0625, 0.166667],
              'ab3': {'tage': 38, 'quote': 0.078947, 'p_shift': 0.8995},
              'erstsignal_ab3': [2, 10],
              'vix_benchmark_ab3': 0.473684,
              'brier': [0.1744, 0.1693],
              'p_T1': 0.7281,
              'p_T3': 0.9534,
              'fwd45_ab3': 0.019795,
              'fwd45_gate': 0.011508},
             {'key': 'E',
              'label': '2007–2016',
              'rolle': 'Entwicklung',
              'gate_tage': 1259,
              'basis': 0.271644,
              'tage': [688, 324, 158, 66, 23],
              'treffer': [164, 79, 52, 30, 17],
              'quote': [0.238372, 0.243827, 0.329114, 0.454545, 0.73913],
              'ab3': {'tage': 89, 'quote': 0.52809, 'p_shift': 0.0193},
              'erstsignal_ab3': [5, 15],
              'vix_benchmark_ab3': 0.191011,
              'brier': [0.1924, 0.1979],
              'p_T1': 0.2458,
              'p_T3': 0.3817,
              'fwd45_ab3': 0.002335,
              'fwd45_gate': 0.009045},
             {'key': 'H1',
              'label': '2017–2026',
              'rolle': 'Holdout, nicht blind',
              'gate_tage': 1556,
              'basis': 0.22108,
              'tage': [723, 496, 222, 84, 31],
              'treffer': [103, 142, 48, 46, 5],
              'quote': [0.142462, 0.28629, 0.216216, 0.547619, 0.16129],
              'ab3': {'tage': 115, 'quote': 0.443478, 'p_shift': 0.009},
              'erstsignal_ab3': [5, 20],
              'vix_benchmark_ab3': 0.234783,
              'brier': [0.1712, 0.1722],
              'p_T1': 0.6051,
              'p_T3': 0.2406,
              'fwd45_ab3': 0.01892,
              'fwd45_gate': 0.018675}],
 'komponenten': {'C': {'H2': [1.38, 0.079], 'E': [1.63, 0.001], 'H1': [1.15, 0.316]},
                 'B': {'H2': [0.77, 0.668], 'E': [1.7, 0.03], 'H1': [1.88, 0.021]},
                 'R': {'H2': [0.9, 0.684], 'E': [1.23, 0.211], 'H1': [1.13, 0.296]},
                 'V': {'H2': [1.0, 0.505], 'E': [1.06, 0.382], 'H1': [1.63, 0.001]},
                 'S': {'H2': [1.43, 0.187], 'E': [1.31, 0.192], 'H1': [1.73, 0.013]},
                 'F': {'H2': [0.88, 0.782], 'E': [0.84, 0.807], 'H1': [1.35, 0.015]},
                 'D': {'H2': [0.46, 0.932], 'E': [1.08, 0.414], 'H1': [1.56, 0.098]}},
 'gesamt': {'gate_tage': 3709,
            'basis': 0.236991,
            'tage': [1901, 1074, 492, 182, 60],
            'treffer': [366, 275, 137, 78, 23],
            'quote': [0.19253, 0.256052, 0.278455, 0.428571, 0.383333],
            'ab3': {'tage': 242, 'quote': 0.417355}}}


@dataclass(frozen=True)
class Params:
    gate_pct: float = 0.03       # SPY hoechstens 3 % unter 252-Tage-Schlusshoch
    gate_lookback: int = 252
    sma: int = 50
    mom: int = 20
    horizon: int = 45            # Sessions fuer die primaere Zielgroesse
    drop: float = 0.05           # >= 5 % unter Schluss t
    episode_gap: int = 20        # Sessions ohne Level >= k vor neuem Episodenstart
    n_placebo: int = 10_000
    seed: int = 20261122
    bh_q: float = 0.10


P = Params()


# --------------------------------------------------------------------------
# Daten
# --------------------------------------------------------------------------
def load_prices(start: str = "2005-01-01", end: str | None = None) -> pd.DataFrame:
    """Bereinigte Tagesschlusskurse von Yahoo. threads=False wegen Streamlit Cloud."""
    import yfinance as yf

    cols = {}
    for t in TICKERS:
        df = yf.download(t, start=start, end=end, auto_adjust=True,
                         progress=False, threads=False)
        if df is None or df.empty:
            raise RuntimeError(f"Keine Daten fuer {t}")
        close = df["Close"]
        if isinstance(close, pd.DataFrame):      # neuere yfinance: MultiIndex-Spalten
            close = close.iloc[:, 0]
        cols[t] = close.astype(float)
    px = pd.DataFrame(cols).sort_index()
    px.index = pd.to_datetime(px.index).tz_localize(None)
    px = px[px["SPY"].notna()]                   # US-Handelstage
    return px


# --------------------------------------------------------------------------
# Modell
# --------------------------------------------------------------------------
def _risk_off(x: pd.Series, p: Params, up_is_risk_off: bool = False) -> pd.Series:
    sma = x.rolling(p.sma).mean()
    chg = x / x.shift(p.mom)
    if up_is_risk_off:
        sig = (x > sma) & (chg > 1)
    else:
        sig = (x < sma) & (chg < 1)
    return sig.where(sma.notna() & chg.notna())  # NaN, solange nicht definiert


def compute_levels(px: pd.DataFrame, p: Params = P) -> pd.DataFrame:
    """Gate, Komponenten und Level je Handelstag."""
    spy = px["SPY"]
    hi = spy.rolling(p.gate_lookback).max()
    out = pd.DataFrame(index=px.index)
    out["spy"] = spy
    out["dist_high"] = spy / hi - 1.0
    out["gate"] = (spy >= (1 - p.gate_pct) * hi).where(hi.notna())
    out["C"] = _risk_off(px["HYG"] / px["IEF"], p)
    out["B"] = _risk_off(px["RSP"], p)
    out["R"] = _risk_off(px["XLY"] / px["XLP"], p)
    out["V"] = _risk_off(px["^VIX"], p, up_is_risk_off=True)
    comp = out[list(COMPONENTS)]
    valid = comp.notna().all(axis=1) & out["gate"].notna()
    out["n_conf"] = comp.astype(float).sum(axis=1).where(valid)
    out["level"] = (out["n_conf"] * out["gate"].astype(float)).where(valid)
    out["valid"] = valid
    return out


def add_outcomes(df: pd.DataFrame, p: Params = P) -> pd.DataFrame:
    """Vorwaerts-Zielgroessen. Nur fuer den Backtest, nie fuer das Level."""
    spy = df["spy"].to_numpy()
    n = len(spy)

    def fwd_min(h: int) -> tuple[np.ndarray, np.ndarray]:
        m = np.full(n, np.nan)
        complete = np.zeros(n, dtype=bool)
        for i in range(n - 1):
            w = spy[i + 1:i + 1 + h]
            m[i] = np.nanmin(w) / spy[i] - 1.0
            complete[i] = len(w) == h
        return m, complete

    out = df.copy()
    dip45, full45 = fwd_min(p.horizon)
    dip10, full10 = fwd_min(10)
    hit45 = dip45 <= -p.drop
    hit10 = dip10 <= -0.03
    # Zensierung: Treffer zaehlt sofort, sonst nur bei vollem Fenster
    out["dip45"] = np.where(full45, dip45, np.nan)
    out["y45"] = np.where(full45 | hit45, hit45.astype(float), np.nan)
    out["y10"] = np.where(full10 | hit10, hit10.astype(float), np.nan)
    return out


def episode_starts(level: pd.Series, k: int, gap: int = P.episode_gap) -> pd.Series:
    """True am ersten Tag mit Level >= k nach `gap` Sessions darunter."""
    prev_max = level.shift(1).rolling(gap).max()
    return ((level >= k) & (prev_max < k)).fillna(False)


def level_markers(level: pd.Series, gap: int = P.episode_gap) -> pd.Series:
    """Level-Marker: Tage, an denen das Level hoeher ist als an den `gap` Sessions davor.

    Das ist das Erstsignal: der Marker traegt das hoechste k, fuer das
    episode_starts(level, k) an diesem Tag wahr ist, also das Level des Tages.
    Rueckgabe: Level an den Marker-Tagen, Index = Datum.
    """
    prev_max = level.shift(1).rolling(gap).max()
    return level[level > prev_max].astype(int)


def sessions_since_warn(level: pd.Series, warn_level: int = WARN_LEVEL) -> pd.Series:
    """Sessions seit dem letzten Tag im Warnzustand (0 am Tag selbst), NaN davor.

    Das Risikofenster ist offen, solange der Wert hoechstens P.horizon betraegt:
    In diesem Fenster misst der Backtest die Rueckgaenge. Kein Ausstiegssignal,
    Kasse im Fenster hat im 26-Jahre-Lauf Rendite gekostet (Regel O2).
    """
    is_warn = (level >= warn_level).fillna(False).to_numpy()
    pos = pd.Series(np.where(is_warn, np.arange(len(level)), np.nan), index=level.index).ffill()
    return pd.Series(np.arange(len(level)), index=level.index, dtype=float) - pos


# --------------------------------------------------------------------------
# Auswertung
# --------------------------------------------------------------------------
def _placebo_p(y_gate: np.ndarray, pos_gate: np.ndarray, n: int, obs_rate: float,
               gap: int, n_draws: int, rng: np.random.Generator) -> float:
    """Anteil zufaelliger Ziehungen (n Gate-Tage, Mindestabstand gap) mit Rate >= obs."""
    if n == 0:
        return np.nan
    ge = 0
    m = len(y_gate)
    for _ in range(n_draws):
        order = rng.permutation(m)
        chosen: list[int] = []
        for j in order:
            pj = pos_gate[j]
            if all(abs(pj - pos_gate[c]) >= gap for c in chosen):
                chosen.append(j)
                if len(chosen) == n:
                    break
        rate = y_gate[chosen].mean()
        if rate >= obs_rate - 1e-12:
            ge += 1
    return (ge + 1) / (n_draws + 1)


def _bh(pvals: dict[int, float], q: float) -> dict[int, bool]:
    items = sorted(((k, v) for k, v in pvals.items() if not np.isnan(v)), key=lambda kv: kv[1])
    m = len(items)
    passed_rank = 0
    for i, (_, pv) in enumerate(items, start=1):
        if pv <= q * i / m:
            passed_rank = i
    return {k: (i <= passed_rank) for i, (k, _) in enumerate(items, start=1)}


def evaluate(df: pd.DataFrame, start: str | None = None, end: str | None = None,
             p: Params = P, with_placebo: bool = True) -> dict:
    """Trefferquoten der Episodenstarts je Schwelle k gegen die Gate-Baseline."""
    d = df[df["valid"]].copy()
    d["pos"] = np.arange(len(d))
    starts = {k: episode_starts(d["level"], k, p.episode_gap) for k in (1, 2, 3, 4)}
    if start:
        sel = d.index >= pd.Timestamp(start)
    else:
        sel = np.ones(len(d), dtype=bool)
    if end:
        sel &= d.index <= pd.Timestamp(end)
    w = d[sel]
    gate_days = w[(w["gate"] == True) & w["y45"].notna()]  # noqa: E712
    base45 = gate_days["y45"].mean()
    base10 = w[(w["gate"] == True) & w["y10"].notna()]["y10"].mean()  # noqa: E712
    base_dip = w[(w["gate"] == True)]["dip45"].median()  # noqa: E712
    rng = np.random.default_rng(p.seed)
    rows, pvals = [], {}
    for k in (1, 2, 3, 4):
        ep = w[starts[k][sel].to_numpy()]
        ep_known = ep[ep["y45"].notna()]
        n = len(ep_known)
        hits = int(ep_known["y45"].sum()) if n else 0
        rate = hits / n if n else np.nan
        pv = np.nan
        if with_placebo and n > 0 and k >= 2:
            pv = _placebo_p(gate_days["y45"].to_numpy(), gate_days["pos"].to_numpy(),
                            n, rate, p.episode_gap, p.n_placebo, rng)
            pvals[k] = pv
        days_k = w[(w["level"] >= k) & w["y45"].notna()]
        rows.append({
            "k": k, "episoden": n, "treffer": hits, "quote": rate,
            "baseline": base45, "p_placebo": pv,
            "quote_y10": ep[ep["y10"].notna()]["y10"].mean() if len(ep) else np.nan,
            "median_dip45": ep["dip45"].median() if len(ep) else np.nan,
            "tage": len(days_k), "quote_tage": days_k["y45"].mean() if len(days_k) else np.nan,
            "starts": [ts.strftime("%Y-%m-%d") for ts in ep.index],
        })
    bh = _bh(pvals, p.bh_q) if pvals else {}
    for r in rows:
        r["bh_signifikant"] = bool(bh.get(r["k"], False))
    return {
        "von": w.index[0].strftime("%Y-%m-%d"), "bis": w.index[-1].strftime("%Y-%m-%d"),
        "jahre": round((w.index[-1] - w.index[0]).days / 365.25, 1),
        "gate_tage": int(len(gate_days)), "baseline_y45": base45,
        "baseline_y10": base10, "baseline_median_dip45": base_dip, "levels": rows,
    }


def current_state(df: pd.DataFrame, p: Params = P) -> dict:
    """Stand am letzten Handelstag fuer die Anzeige."""
    d = df[df["valid"]]
    last = d.iloc[-1]
    lvl = int(last["level"])
    since = None
    if lvl > 0:
        below = d["level"] < lvl
        idx = np.where(below.to_numpy())[0]
        since = d.index[idx[-1] + 1] if len(idx) and idx[-1] + 1 < len(d) else d.index[0]
    return {
        "datum": d.index[-1], "level": lvl, "gate": bool(last["gate"]),
        "dist_high": float(last["dist_high"]),
        "komponenten": {c: bool(last[c]) for c in COMPONENTS},
        "n_conf": int(last["n_conf"]),
        "level_seit": since,
    }



def forward_track(df: pd.DataFrame, since: str = FREEZE_DATE, warn_level: int = WARN_LEVEL) -> pd.DataFrame:
    """Tage im Warnzustand nach dem Einfrieren, mit Ausgang soweit bekannt (Live-Test).

    `df` muss aus add_outcomes(compute_levels(px)) stammen.
    """
    d = df[df["valid"] & (df.index > pd.Timestamp(since))]
    d = d[(d["gate"] == True) & (d["level"] >= warn_level)]  # noqa: E712
    out = pd.DataFrame({
        "level": d["level"].astype(int),
        "komponenten": d[list(COMPONENTS)].apply(
            lambda r: "".join(c for c in COMPONENTS if r[c] == True), axis=1) if len(d) else pd.Series(dtype=str),  # noqa: E712
        "spy": d["spy"],
        "y45": d["y45"],
    })
    return out


def forward_summary(track: pd.DataFrame) -> dict:
    known = track[track["y45"].notna()]
    return {"tage": int(len(track)), "bekannt": int(len(known)), "treffer": int(known["y45"].sum()),
            "offen": int(len(track) - len(known))}
