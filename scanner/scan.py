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
    with open(path, encoding="utf-8") as f:
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
    return m


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
        "Perf1M%": last["ret21"] * 100,
        "Perf3M%": last["ret63"] * 100,
        "Perf6M%": last["ret126"] * 100,
        "FromHigh%": (last["C"] / hi - 1) * 100,
    })
    snap.index.name = "Ticker"
    meta = master.set_index("Ticker")[
        ["Name", "Exchange", "Sector", "Industry", "MarketCap",
         "SP500", "NASDAQ", "R2000"]]
    snap = meta.join(snap, how="inner").reset_index()
    return snap[snap["Price"].notna()]
