"""Indikatoren und Breadth-Zeitreihen – vektorisiert ueber alle Titel.

Alle Kennzahlen je Handelstag. Definitionen:
    adv/dec        Close vs. Vortags-Close
    up_vol/dn_vol  Richtung wie A/D UND Volumen > 50-Tage-Schnitt
    up4/dn4        Tagesaenderung >= +4 % / <= -4 % bei Volumen > Vortag
                   und >= 100k Stueck (Stockbee-Definition)
    up25q/dn25q    +-25 % in 65 Handelstagen (Quartal)
    up13_34/dn13_34  +-13 % in 34 Handelstagen
    nh/nl          Close ueber/unter dem 252-Tage-Hoch/Tief (exkl. heute)
    p_ab20..200    % der Titel ueber SMA20/40/50/200 (p_ab40 = T2108)
    p_stack        % mit EMA10 > EMA20 > SMA50
    p_s1..p_s4     Weinstein-Stages (SMA200 + 20-Tage-Steigung)
"""
import numpy as np
import pandas as pd


def compute_indicators(px: dict) -> dict:
    C = px["Close"].ffill(limit=5)            # Einzelluecken von Yahoo ueberbruecken
    gap = px["Close"].isna() & C.notna()
    H = px["High"].where(~gap, C).fillna(C)
    L = px["Low"].where(~gap, C).fillna(C)
    V = px["Volume"].where(~gap, 0.0)
    prev = C.shift(1)

    ind = {"C": C, "H": H, "L": L, "V": V}
    ind["chg"] = C / prev - 1
    for n in (20, 40, 50, 200):
        ind[f"sma{n}"] = C.rolling(n, min_periods=n).mean()
    for n in (10, 20):
        ind[f"ema{n}"] = C.ewm(span=n, adjust=False, min_periods=n).mean()

    tr = np.fmax(np.fmax((H - L).to_numpy(), (H - prev).abs().to_numpy()),
                 (L - prev).abs().to_numpy())
    tr = pd.DataFrame(tr, index=C.index, columns=C.columns)
    ind["atr14"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()

    ind["vol50"] = V.shift(1).rolling(50, min_periods=50).mean()
    ind["dvol20"] = (C * V).rolling(20, min_periods=20).mean()
    ind["hi252"] = H.shift(1).rolling(252, min_periods=252).max()
    ind["lo252"] = L.shift(1).rolling(252, min_periods=252).min()
    for n in (21, 34, 63, 65, 126):
        ind[f"ret{n}"] = C / C.shift(n) - 1
    ind["slope200"] = ind["sma200"] / ind["sma200"].shift(20) - 1
    return ind


def stages(ind: dict) -> tuple:
    """Weinstein-Naeherung wie im bisherigen Breadth-Tab."""
    C, s200, slope = ind["C"], ind["sma200"], ind["slope200"]
    valid = s200.notna() & slope.notna()
    above = C > s200
    rising, falling = slope > 0.002, slope < -0.002
    return (valid & ~above & ~falling, valid & above & rising,
            valid & above & ~rising, valid & ~above & falling, valid)


def breadth(ind: dict, cols: list, mask: pd.DataFrame | None = None) -> pd.DataFrame:
    """Breadth-Zeitreihe fuer eine Titelmenge. mask (Datum x Ticker, bool)
    erlaubt dynamische Universen (z.B. taegliche Scanner-Treffer)."""
    cols = [c for c in cols if c in ind["C"].columns]
    g = {k: v[cols] for k, v in ind.items()}
    valid = g["C"].notna() & g["chg"].notna()
    if mask is not None:
        valid &= mask[cols]

    def cnt(cond):
        return (cond & valid).sum(axis=1)

    def pct(cond, base):
        b = (base & valid).sum(axis=1)
        return (100.0 * (cond & base & valid).sum(axis=1) / b.where(b > 0)).round(2)

    C, V, chg = g["C"], g["V"], g["chg"]
    hivol = V > g["vol50"]
    vol_up = (V > V.shift(1)) & (V >= 100_000)
    s1, s2, s3, s4, sv = stages(g)

    out = pd.DataFrame({
        "n": cnt(valid),
        "adv": cnt(chg > 0), "dec": cnt(chg < 0),
        "up_vol": cnt((chg > 0) & hivol), "dn_vol": cnt((chg < 0) & hivol),
        "up4": cnt((chg >= 0.04) & vol_up), "dn4": cnt((chg <= -0.04) & vol_up),
        "up25q": cnt(g["ret65"] >= 0.25), "dn25q": cnt(g["ret65"] <= -0.25),
        "up13_34": cnt(g["ret34"] >= 0.13), "dn13_34": cnt(g["ret34"] <= -0.13),
        "nh": cnt(C > g["hi252"]), "nl": cnt(C < g["lo252"]),
        "p_ab20": pct(C > g["sma20"], g["sma20"].notna()),
        "p_ab40": pct(C > g["sma40"], g["sma40"].notna()),
        "p_ab50": pct(C > g["sma50"], g["sma50"].notna()),
        "p_ab200": pct(C > g["sma200"], g["sma200"].notna()),
        "p_stack": pct((g["ema10"] > g["ema20"]) & (g["ema20"] > g["sma50"]),
                       g["sma50"].notna()),
        "p_s1": pct(s1, sv), "p_s2": pct(s2, sv),
        "p_s3": pct(s3, sv), "p_s4": pct(s4, sv),
    })
    out.index.name = "date"
    return out


def weekly(daily: pd.DataFrame, ind: dict, cols: list,
           mask: pd.DataFrame | None = None) -> pd.DataFrame:
    """Wochenwerte: Zustaende (p_*) = letzter Tag der Woche, Ereignisse
    (up4, nh, ...) = Wochensumme, A/D = Wochen-Close vs. Vorwochen-Close."""
    cols = [c for c in cols if c in ind["C"].columns]
    wk = daily.index.to_period("W-FRI")
    level_cols = [c for c in daily.columns if c.startswith("p_")] + ["n"]
    sum_cols = ["up_vol", "dn_vol", "up4", "dn4", "nh", "nl"]
    last_cols = ["up25q", "dn25q", "up13_34", "dn13_34"]
    agg = daily.groupby(wk).agg(
        {**{c: "last" for c in level_cols + last_cols},
         **{c: "sum" for c in sum_cols}})

    C = ind["C"][cols]
    valid = C.notna()
    if mask is not None:
        valid &= mask[cols]
    cw = C.groupby(C.index.to_period("W-FRI")).last()
    vw = valid.groupby(valid.index.to_period("W-FRI")).last()
    wchg = cw / cw.shift(1) - 1
    agg["adv"] = ((wchg > 0) & vw).sum(axis=1).reindex(agg.index)
    agg["dec"] = ((wchg < 0) & vw).sum(axis=1).reindex(agg.index)

    # Datum = letzter tatsaechlicher Handelstag der Woche
    last_day = pd.Series(daily.index, index=wk).groupby(level=0).last()
    agg.index = pd.DatetimeIndex(last_day.reindex(agg.index).values, name="date")
    return agg[daily.columns]
