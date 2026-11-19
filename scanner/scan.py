"""Eigener Scanner -> eigene Universumsliste.

Kennzahlen je Titel (Stand letzter Handelstag):
    ATR%       ATR14 / Close * 100
    Gain50%    (Close / SMA50 - 1) * 100
    ATRx50     Gain50% / ATR%  ("ATR% multiple from 50-MA")
    AVOL       Ø Volumen 50 Tage (Stueck), AVOL$ = Ø Dollar-Volumen 20 Tage
    RVOL       Volumen heute / AVOL
    Trend      Weinstein-Stage (1-4) sowie SMA50 > SMA200
    RS         IBD-Stil (40/20/20/20) als Perzentil gegen das Gesamtuniversum

Die Filter werden als Maske (Datum x Ticker) ueber die ganze Historie
berechnet. So hat auch die Scanner-Liste eine Breadth-Historie und man sieht,
wie viele Titel an jedem Tag durch den Scan gekommen waeren. Market Cap ist
dabei der aktuelle Wert (keine historische Market Cap verfuegbar).
"""
import json

import numpy as np
import pandas as pd

from . import CONFIG_FILE
from .metrics import stages

TRENDS = {
    None: "aus",
    "stage2": "Stage 2 (ueber steigender SMA200)",
    "sma50_above_sma200": "SMA50 > SMA200",
    "above_sma200": "Close > SMA200",
}


def load_config(path: str = CONFIG_FILE) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        cfg = json.load(f)
    return {k: v for k, v in cfg.items() if not k.startswith("_")}


def derived(ind: dict) -> dict:
    C = ind["C"]
    atr_pct = ind["atr14"] / C * 100
    gain50 = (C / ind["sma50"] - 1) * 100
    return {
        "atr_pct": atr_pct,
        "gain50": gain50,
        "atrx50": gain50 / atr_pct.where(atr_pct > 0),
        "rvol": ind["V"] / ind["vol50"].where(ind["vol50"] > 0),
    }


def scan_mask(ind: dict, master: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    C = ind["C"]
    d = derived(ind)
    m = C.notna()

    def rng(frame, lo, hi):
        nonlocal m
        if lo is not None:
            m &= frame >= lo
        if hi is not None:
            m &= frame <= hi

    rng(C, cfg.get("min_price"), None)
    rng(ind["vol50"], cfg.get("min_avol"), None)
    rng(d["rvol"], cfg.get("min_rvol"), None)
    rng(d["atr_pct"], cfg.get("min_atr_pct"), cfg.get("max_atr_pct"))
    rng(d["gain50"], cfg.get("min_gain50"), cfg.get("max_gain50"))
    rng(d["atrx50"], cfg.get("min_atrx50"), cfg.get("max_atrx50"))
    if cfg.get("close_above_ema10"):
        m &= C > ind["ema10"]
    if cfg.get("close_above_ema20"):
        m &= C > ind["ema20"]
    if cfg.get("ema10_20_above_sma50"):
        m &= (ind["ema10"] > ind["sma50"]) & (ind["ema20"] > ind["sma50"])

    trend = cfg.get("trend")
    if trend == "stage2":
        m &= stages(ind)[1]
    elif trend == "sma50_above_sma200":
        m &= ind["sma50"] > ind["sma200"]
    elif trend == "above_sma200":
        m &= C > ind["sma200"]

    if cfg.get("min_market_cap"):
        cap = master.set_index("Ticker")["MarketCap"].reindex(C.columns)
        m.loc[:, ~(cap >= cfg["min_market_cap"]).to_numpy()] = False
    # "One Rule": nur Titel aus fuehrenden Industrien (Industrie-RS-Perzentil).
    # Wie die Market Cap ein heutiger Wert – rueckwirkend nicht historisch.
    if cfg.get("min_industry_rs") and "IndRS" in master.columns:
        irs = master.set_index("Ticker")["IndRS"].reindex(C.columns)
        m.loc[:, ~(irs >= cfg["min_industry_rs"]).to_numpy()] = False
    return m


# Fenster und Gewichte des RS-Mix wie im 14-Uhr-Briefing ("Branchen-Staerke")
RS_WINDOWS = {"d": 1, "w": 5, "m": 21, "q": 63, "h": 126, "y": 252}
RS_WEIGHTS = {"w": 1, "m": 2, "q": 3, "h": 2, "y": 1}


def rank99(s: pd.Series) -> pd.Series:
    """Rang 0-99 wie im Briefing: bester Wert 99, schlechtester 0."""
    n = int(s.notna().sum())
    if n < 2:
        return pd.Series(99.0, index=s.index).where(s.notna())
    return ((s.rank(method="average") - 1) / (n - 1) * 99).round()


def _group_rs(rows: pd.DataFrame, key: str, min_n: int) -> pd.DataFrame:
    """Je Gruppe: Median der Mitglieder je Fenster, daraus Raenge, Mix und RS."""
    grp = rows.groupby(key)
    tbl = pd.DataFrame({"n": grp.size()})
    for k in RS_WINDOWS:
        tbl[f"med_{k}"] = grp[k].median()
    tbl = tbl[tbl["n"] >= min_n].copy()
    for k in RS_WINDOWS:
        tbl[k] = rank99(tbl[f"med_{k}"])
    tbl["comp"] = (sum(tbl[k] * w for k, w in RS_WEIGHTS.items())
                   / sum(RS_WEIGHTS.values())).round(2)
    tbl["rs"] = rank99(tbl["comp"])
    return tbl


def industry_rs(ind: dict, master: pd.DataFrame, min_n: int = 3,
                min_cap: float = 1e9) -> tuple:
    """Relative Staerke je Industrie und je Sektor – der RS-Baustein des
    14-Uhr-Briefings (nach Steve Jacobs' "One Rule").

    Grundlage ist das Universum ab `min_cap` Boersenwert mit der
    Nasdaq-Brancheneinteilung. Je Gruppe zaehlt der Median der Mitglieder
    ueber Tag/Woche/Monat/Quartal/Halbjahr/Jahr; jedes Fenster wird ueber
    alle Gruppen als Rang 0-99 gewertet. Mix = Woche 1, Monat 2, Quartal 3,
    Halbjahr 2, Jahr 1; der Rang des Mix ist der RS. Sektoren bekommen
    zusaetzlich den Quadranten aus Woche gegen Monat (stark / verbessert /
    schwaecht ab / schwach, Grenze jeweils Rang 50).

    Rueckgabe: (Industrie-Tabelle, Sektor-Tabelle, IndRS je Ticker). Der
    IndRS gilt auch fuer Titel unter `min_cap` – ueber ihre Industrie.
    """
    C = ind["C"]
    rows = pd.DataFrame({k: ind[f"ret{n}"].iloc[-1] * 100
                         for k, n in RS_WINDOWS.items() if k != "d"})
    rows["d"] = ind["chg"].iloc[-1] * 100
    rows["dv20"] = ind["dvol20"].iloc[-1]
    meta = master.set_index("Ticker")[["Sector", "Industry", "MarketCap"]]
    rows = rows.join(meta.reindex(C.columns))
    rows = rows[(rows["MarketCap"] >= min_cap)
                & rows["Industry"].notna() & (rows["Industry"] != "Unknown")]

    ind_tbl = _group_rs(rows, "Industry", min_n)
    ind_tbl["Sector"] = rows.groupby("Industry")["Sector"].agg(
        lambda s: s.mode().iloc[0] if len(s.dropna()) else "")
    by_dv = rows.sort_values("dv20", ascending=False).reset_index()
    ind_tbl["syms"] = by_dv.groupby("Industry")["Ticker"].agg(
        lambda t: "|".join(t.head(8)))
    ind_tbl = (ind_tbl.rename(columns={"rs": "IndRS"})
               .sort_values(["IndRS", "comp"], ascending=False))
    ind_tbl.index.name = "Industry"

    sec_rows = rows[rows["Sector"].notna() & (rows["Sector"] != "Unknown")]
    sec_tbl = _group_rs(sec_rows, "Sector", min_n).rename(columns={"rs": "SecRS"})
    w_ok, m_ok = sec_tbl["w"] >= 50, sec_tbl["m"] >= 50
    sec_tbl["Quadrant"] = np.select(
        [w_ok & m_ok, w_ok & ~m_ok, ~w_ok & m_ok],
        ["stark", "verbessert", "schwaecht ab"], default="schwach")
    sec_tbl = sec_tbl.sort_values(["SecRS", "comp"], ascending=False)
    sec_tbl.index.name = "Sector"

    order = ["n", "comp"] + list(RS_WINDOWS) + [f"med_{k}" for k in RS_WINDOWS]
    ind_out = ind_tbl.reset_index()[["Industry", "Sector", "IndRS"] + order + ["syms"]]
    sec_out = sec_tbl.reset_index()[["Sector", "SecRS", "Quadrant"] + order]
    per_ticker = meta.reindex(C.columns)["Industry"].map(
        ind_tbl["IndRS"])
    return ind_out, sec_out, per_ticker


def snapshot(ind: dict, master: pd.DataFrame) -> pd.DataFrame:
    """Alle Scanner-Kennzahlen fuer den letzten Handelstag, je Titel."""
    d = derived(ind)
    last = {k: v.iloc[-1] for k, v in ind.items()}
    dl = {k: v.iloc[-1] for k, v in d.items()}
    s1, s2, s3, s4, sv = (x.iloc[-1] for x in stages(ind))
    stage = pd.Series(np.nan, index=ind["C"].columns)
    for i, s in enumerate((s1, s2, s3, s4), start=1):
        stage[s] = i

    # IBD-Stil RS (Quartale ueber ret63-Ketten)
    C = ind["C"]
    q = [C.iloc[-1] / C.iloc[-64] - 1, C.iloc[-64] / C.iloc[-127] - 1,
         C.iloc[-127] / C.iloc[-190] - 1, C.iloc[-190] / C.iloc[-253] - 1] \
        if len(C) >= 253 else None
    rs = pd.Series(np.nan, index=C.columns)
    if q is not None:
        score = 0.4 * q[0] + 0.2 * q[1] + 0.2 * q[2] + 0.2 * q[3]
        rs = (score.rank(pct=True) * 98 + 1).round()

    hi = ind["H"].iloc[-252:].max()
    snap = pd.DataFrame({
        "Price": last["C"],
        "Chg%": last["chg"] * 100,
        "ATR%": dl["atr_pct"],
        "Gain50%": dl["gain50"],
        "ATRx50": dl["atrx50"],
        "AVOL": last["vol50"],
        "AVOL$": last["dvol20"],
        "RVOL": dl["rvol"],
        "EMA10": last["ema10"], "EMA20": last["ema20"],
        "SMA50": last["sma50"], "SMA200": last["sma200"],
        "Stage": stage,
        "RS": rs,
        "Perf1W%": last["ret5"] * 100,
        "Perf1M%": last["ret21"] * 100,
        "Perf3M%": last["ret63"] * 100,
        "Perf6M%": last["ret126"] * 100,
        "FromHigh%": (last["C"] / hi - 1) * 100,
    })
    snap.index.name = "Ticker"
    # Unterphase wie in der App (Stage-Analyse): 2B/4B = neues 20-Tage-
    # Hoch/-Tief, 2C/4C = 3 ATR vom EMA10, 1B/3A = ueber SMA50
    ext10 = (last["C"] - last["ema10"]) / last["atr14"].where(last["atr14"] > 0)
    sma50, hi20, lo20 = last["sma50"], last["hi20"], last["lo20"]
    sub = pd.Series("", index=C.columns, dtype=object)
    sub[s1] = np.where(last["C"][s1] > sma50[s1], "1B", "1A")
    sub[s2] = np.where(ext10[s2] >= 3, "2C",
                       np.where(last["C"][s2] > hi20[s2], "2B", "2A"))
    sub[s3] = np.where(last["C"][s3] >= sma50[s3], "3A", "3B")
    sub[s4] = np.where(ext10[s4] <= -3, "4C",
                       np.where(last["C"][s4] < lo20[s4], "4B", "4A"))
    snap["SubStage"] = sub.replace("", np.nan)
    cols = ["Name", "Exchange", "Sector", "Industry", "MarketCap",
            "SP500", "NASDAQ", "R2000"] + (["IndRS"] if "IndRS" in master else [])
    meta = master.set_index("Ticker")[cols]
    snap = meta.join(snap, how="inner").reset_index()
    return snap[snap["Price"].notna()]
