"""Forschungsbibliothek fuer Protokoll v1.1. Nur Bausteine, keine Auswertung beim Import."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import correction_risk as cr  # noqa: E402

SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
COMPS4 = ["C", "B", "R", "V"]
COMPS7 = ["C", "B", "R", "V", "S", "F", "D"]
SEED = 20261122
E_START, E_END = "2007-06-20", "2016-12-30"
H1_START = "2017-01-03"
H2_END = "2007-06-19"
MODELS = {
    "M1": ["logvix"],
    "M2": ["logvix", "dist_high"],
    "M3": ["logvix", "n4"],
    "M4": ["logvix", "n7"],
    "M5": ["logvix", "n4s"],
    "M6": ["logvix", "n7s"],
    "M7": ["logvix", "nSel"],
    "M8": ["logvix", "dist_high", "n7"],
}


# ------------------------------------------------------------------ Daten
def chain(px: pd.DataFrame, primary: str, proxy: str) -> pd.Series:
    """Verkettete Renditereihe: Rendite des ETF, davor die des Proxys."""
    rp = px[primary].pct_change()
    rx = px[proxy].pct_change()
    use_primary = px[primary].notna() & px[primary].shift(1).notna()
    r = rp.where(use_primary, rx)
    first = r.first_valid_index()
    lvl = (1.0 + r.fillna(0.0)).cumprod()
    lvl[lvl.index < first] = np.nan
    return lvl


def _off(x: pd.Series, up: bool = False, sma: int = 50, mom: int = 20) -> pd.Series:
    s = x.rolling(sma).mean()
    c = x / x.shift(mom)
    sig = ((x > s) & (c > 1)) if up else ((x < s) & (c < 1))
    return sig.where(s.notna() & c.notna())


def build(px: pd.DataFrame) -> pd.DataFrame:
    """Alle Merkmale und Zielgroessen, kausal. Verkettete Reihen fuer die Proxy-Aera."""
    spy = px["SPY"]
    hyg, ief = chain(px, "HYG", "VWEHX"), chain(px, "IEF", "VFITX")
    rsp, iwm = chain(px, "RSP", "VADAX"), chain(px, "IWM", "^RUT")
    hi = spy.rolling(252).max()
    d = pd.DataFrame(index=px.index)
    d["spy"] = spy
    d["vix"] = px["^VIX"]
    d["logvix"] = np.log(px["^VIX"])
    d["dist_high"] = spy / hi - 1.0
    d["gate"] = (spy >= 0.97 * hi).where(hi.notna())
    d["C"] = _off(hyg / ief)
    d["B"] = _off(rsp)
    d["R"] = _off(px["XLY"] / px["XLP"])
    d["V"] = _off(px["^VIX"], up=True)
    d["S"] = _off(iwm)
    d["F"] = _off(px["XLF"] / spy)
    below = pd.concat([(px[s] < px[s].rolling(50).mean()).where(px[s].rolling(50).mean().notna())
                       for s in SECTORS], axis=1)
    cnt = below.astype(float).sum(axis=1).where(below.notna().all(axis=1))
    d["D"] = (cnt >= 5).where(cnt.notna())
    ok = d[COMPS7].notna().all(axis=1) & d["gate"].notna()
    d["n4"] = d[COMPS4].astype(float).sum(axis=1).where(ok)
    d["n7"] = d[COMPS7].astype(float).sum(axis=1).where(ok)
    d["n4s"] = d["n4"].rolling(10).mean()
    d["n7s"] = d["n7"].rolling(10).mean()
    d["valid"] = ok & d["n7s"].notna()
    d["level_v10"] = (d["n4"] * d["gate"].astype(float)).where(ok)
    d = cr.add_outcomes(d)
    d["fwd45"] = spy.shift(-45) / spy - 1.0
    d["pos"] = np.arange(len(d))
    return d


def segment(d: pd.DataFrame, name: str) -> pd.DataFrame:
    """Gate-Tage mit bekanntem Ausgang in der Stichprobe (zeitlich sortiert)."""
    v = d[d["valid"]]
    if name == "E":
        last_pos = d.loc[:E_END, "pos"].iloc[-1]
        m = (v.index >= E_START) & (v["pos"] + 45 <= last_pos)
    elif name == "H1":
        m = v.index >= H1_START
    elif name == "H2":
        last_pos = d.loc[:H2_END, "pos"].iloc[-1]
        m = v["pos"] + 45 <= last_pos
    else:
        raise ValueError(name)
    w = v[m]
    return w[(w["gate"] == True) & w["y45"].notna()]  # noqa: E712


def all_days(d: pd.DataFrame, name: str) -> pd.DataFrame:
    """Alle gueltigen Tage der Stichprobe (auch ausserhalb Gate), fuer Episoden."""
    v = d[d["valid"]]
    if name == "E":
        last_pos = d.loc[:E_END, "pos"].iloc[-1]
        return v[(v.index >= E_START) & (v["pos"] + 45 <= last_pos)]
    if name == "H1":
        return v[v.index >= H1_START]
    last_pos = d.loc[:H2_END, "pos"].iloc[-1]
    return v[v["pos"] + 45 <= last_pos]


# ------------------------------------------------------------------ Modell
def fit_logit(X: np.ndarray, y: np.ndarray, l2: float = 1e-8) -> np.ndarray:
    Xb = np.column_stack([np.ones(len(X)), X])
    w = np.zeros(Xb.shape[1])
    for _ in range(200):
        p = 1.0 / (1.0 + np.exp(-Xb @ w))
        g = Xb.T @ (p - y) + l2 * w
        H = (Xb.T * (p * (1 - p))) @ Xb + l2 * np.eye(len(w))
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-10:
            break
    return w


def predict(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    Xb = np.column_stack([np.ones(len(X)), X])
    return 1.0 / (1.0 + np.exp(-Xb @ w))


def select_comps(train: pd.DataFrame, min_lift: float = 1.25, min_n: int = 50) -> list[str]:
    base = train["y45"].mean()
    keep = []
    for c in COMPS7:
        on = train[train[c] == True]  # noqa: E712
        if len(on) >= min_n and base > 0 and on["y45"].mean() / base >= min_lift:
            keep.append(c)
    return keep


def with_nsel(df: pd.DataFrame, comps: list[str]) -> pd.DataFrame:
    out = df.copy()
    out["nSel"] = out[comps].astype(float).sum(axis=1) if comps else 0.0
    return out


# ------------------------------------------------------------------ Masse
def logloss(y, p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def brier(y, p):
    return float(((p - y) ** 2).mean())


def auc(y, s):
    from scipy.stats import rankdata
    y = np.asarray(y)
    r = rankdata(s)
    n1, n0 = y.sum(), len(y) - y.sum()
    if n1 == 0 or n0 == 0:
        return np.nan
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def shift_test(y: np.ndarray, state: np.ndarray, min_off: int = 60) -> tuple[float, float, int]:
    """Zirkulaerer Shift-Test: Zustand gegen Ausgang ueber die Gate-Tag-Folge verschieben."""
    n = len(y)
    k = int(state.sum())
    if k == 0:
        return np.nan, np.nan, 0
    obs = y[state].mean()
    ge, tot = 0, 0
    for off in range(min_off, n - min_off + 1):
        tot += 1
        if y[np.roll(state, off)].mean() >= obs - 1e-12:
            ge += 1
    return float(obs), (ge + 1) / (tot + 1), k


def block_boot_brier(y: np.ndarray, p_model: np.ndarray, p_ref: np.ndarray | None,
                     block: int = 60, reps: int = 5000, seed: int = SEED) -> dict:
    """Moving-Block-Bootstrap der Brier-Differenz Modell minus Referenz (beide Prognosen fest).
    p_ref=None: Referenz ist die Konstante = Basisrate der Stichprobe (Protokoll Abschnitt 8)."""
    rng = np.random.default_rng(seed)
    n = len(y)
    nb = int(np.ceil(n / block))
    starts_max = n - block
    if p_ref is None:
        p_ref = np.full(n, y.mean())
    d_obs = brier(y, p_model) - brier(y, p_ref)
    diffs = np.empty(reps)
    for i in range(reps):
        st = rng.integers(0, starts_max + 1, nb)
        idx = (st[:, None] + np.arange(block)[None, :]).ravel()[:n]
        diffs[i] = brier(y[idx], p_model[idx]) - brier(y[idx], p_ref[idx])
    return {"delta": float(d_obs), "p_one_sided": float((np.sum(diffs >= 0) + 1) / (reps + 1)),
            "ci90": [float(np.quantile(diffs, 0.05)), float(np.quantile(diffs, 0.95))]}


def bh(pvals: dict[str, float], q: float = 0.10) -> dict[str, bool]:
    items = sorted(((k, v) for k, v in pvals.items() if v is not None and not np.isnan(v)), key=lambda kv: kv[1])
    m = len(items)
    passed = 0
    for i, (_, pv) in enumerate(items, start=1):
        if pv <= q * i / m:
            passed = i
    return {k: (i <= passed) for i, (k, _) in enumerate(items, start=1)}


def levels_from_p(p: np.ndarray, cuts: list[float]) -> np.ndarray:
    return np.searchsorted(np.asarray(cuts), p, side="right")
