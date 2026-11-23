"""Level-Steckbriefe: die Kennzahlen der TSF-Blaetter fuer den Eigenbau.
Aufruf: python level_steckbriefe.py <datenordner>
Beschreibend. Mehrere Kennzahlen je Level, keine Korrektur fuer Mehrfachvergleiche, kein Test.
Erwartet levels_py.csv aus nasdaq_variante.py."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

data = Path(sys.argv[1])
d = pd.read_csv(data / "levels_py.csv", index_col=0, parse_dates=True)
px = d["spy"].to_numpy()
n = len(px)


def worst_dip(h: int) -> tuple[np.ndarray, np.ndarray]:
    dip, full = np.full(n, np.nan), np.zeros(n, dtype=bool)
    for i in range(n - 1):
        w = px[i + 1:i + 1 + h]
        if np.isnan(px[i]) or np.isnan(w).all():
            continue
        dip[i] = np.nanmin(w) / px[i] - 1.0
        full[i] = len(w) == h
    return dip, full


def flag(h: int, drop: float) -> pd.Series:
    """Treffer zaehlt sofort, kein Treffer erst mit vollem Fenster (wie add_outcomes)."""
    dip, full = worst_dip(h)
    hit = dip <= -drop
    y = np.where(full | hit, hit.astype(float), np.nan)
    y[np.isnan(dip)] = np.nan
    return pd.Series(y, index=d.index)


Y = pd.DataFrame({"3%/10": flag(10, .03), "3%/30": flag(30, .03), "5%/45": flag(45, .05),
                  "5%/63": flag(63, .05), "10%/30": flag(30, .10)})
dip45, full45 = worst_dip(45)
DIP = pd.Series(np.where(full45, dip45, np.nan), index=d.index)

lvl = d["level_v10"]
gate = (d["gate"] == True)                                   # noqa: E712
valid = lvl.notna()


def starts(k: int) -> pd.Series:
    prev = lvl.shift(1).rolling(20).max()
    return ((lvl >= k) & (prev < k)).fillna(False)


def row(mask: pd.Series, a: str, b: str) -> dict:
    m = mask & valid
    m = m.loc[a:b]
    idx = m.index[m.to_numpy()]
    r = {"n": int(len(idx)), "pro_jahr": round(len(idx) / ((pd.Timestamp(b) - pd.Timestamp(a)).days / 365.25), 2)}
    for c in Y:
        y = Y.loc[idx, c].dropna()
        r[c] = None if len(y) == 0 else round(float(y.mean()), 4)
        r[c + "_k"] = f"{int(y.sum())}/{len(y)}"
    dd = DIP.loc[idx].dropna()
    r["median_dip45"] = None if len(dd) == 0 else round(float(dd.median()), 4)
    return r


def block(a: str, b: str) -> dict:
    out = {"Basis (alle Gate-Tage)": row(gate, a, b)}
    for k in (1, 2, 3, 4):
        out[f"Zustand Level {k}"] = row(gate & (lvl == k), a, b)
    out["Zustand Warnzustand (ab 3)"] = row(gate & (lvl >= 3), a, b)
    for k in (1, 2, 3, 4):
        out[f"Marker ab Level {k}"] = row(starts(k), a, b)
    return out


def show(title: str, blk: dict) -> None:
    print(f"\n{title}")
    print(f"{'':30s}{'n':>6s}{'/Jahr':>7s}" + "".join(f"{c:>9s}" for c in Y) + f"{'med.Dip45':>11s}")
    for name, r in blk.items():
        cells = "".join(f"{(r[c] * 100 if r[c] is not None else float('nan')):8.1f}%" for c in Y)
        md = f"{r['median_dip45'] * 100:9.1f}%" if r["median_dip45"] is not None else f"{'–':>10s}"
        print(f"{name:30s}{r['n']:6d}{r['pro_jahr']:7.2f}{cells}{md}")


res = {"tsf_zeitraum_2012_2026": block("2012-01-03", "2026-07-31"), "voll_2000_2026": block("2000-01-03", "2026-11-20")}
show("Zeitraum wie TSF: 03.01.2012 bis 31.07.2026", res["tsf_zeitraum_2012_2026"])
show("Voller Zeitraum: 03.01.2000 bis 20.11.2026", res["voll_2000_2026"])
print("\nZähler 5%/45, Zeitraum wie TSF:", {k: v["5%/45_k"] for k, v in res["tsf_zeitraum_2012_2026"].items()})

# Stand des Risikofensters: Sessions seit dem letzten Tag im Warnzustand, beide Indizes
for name, col in (("S&P 500", "level_v10"), ("NASDAQ", "levelN")):
    w = (d[col] >= 3).fillna(False).to_numpy()
    since = np.full(n, np.nan)
    last = None
    for i in range(n):
        if w[i]:
            last = i
        if last is not None:
            since[i] = i - last
    s = pd.Series(since, index=d.index)
    d["since_" + col] = s
    w500 = s.iloc[-500:]
    print(f"{name}: letzter Warntag {d.index[np.where(w)[0][-1]].date()}, Sessions seither {int(s.iloc[-1])}, "
          f"Fenstertage (<=45) in den letzten 500 Tagen: {int((w500 <= 45).sum())}")
    res[f"fenster_{name}"] = {"letzter_warntag": str(d.index[np.where(w)[0][-1]].date()), "seit": int(s.iloc[-1]),
                              "fenstertage_500": int((w500 <= 45).sum())}
d[["since_level_v10", "since_levelN"]].to_csv(data / "since_warn.csv")
(data / "results_steckbriefe.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
print("geschrieben: results_steckbriefe.json, since_warn.csv")
