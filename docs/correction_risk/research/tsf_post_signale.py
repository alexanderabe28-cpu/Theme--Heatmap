"""Zwei Signale aus dem TSF-Rueckblick (RSP ueberdehnt, Flucht aus High Beta) ueber die Historie.
Aufruf: python tsf_post_signale.py <datenordner>
Festlegung vorab in TSF_POST_SIGNALE.md. Beschreibend, ein Lauf.
Erwartet levels_py.csv aus nasdaq_variante.py. Laedt RSP (OHLC), SPHB, SPHQ nach post_signale_px.csv."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crlib import shift_test  # noqa: E402

data = Path(sys.argv[1])
PX = data / "post_signale_px.csv"
if not PX.exists():
    import yfinance as yf
    out = {}
    for t in ["RSP", "SPHB", "SPHQ"]:
        df = yf.download(t, start="2003-01-01", auto_adjust=True, progress=False, threads=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        for c in ["High", "Low", "Close"]:
            out[f"{t}_{c}"] = df[c].astype(float)
    p = pd.DataFrame(out)
    p.index = pd.to_datetime(p.index).tz_localize(None)
    p.to_csv(PX)

p = pd.read_csv(PX, index_col=0, parse_dates=True)
d = pd.read_csv(data / "levels_py.csv", index_col=0, parse_dates=True)
p = p.reindex(d.index)

# ---- Signal X: RSP ueberdehnt
c, h, l = p["RSP_Close"], p["RSP_High"], p["RSP_Low"]
tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
tr[c.shift(1).isna()] = np.nan
first = tr.first_valid_index()
atr = tr.loc[first:].ewm(alpha=1 / 14, adjust=False, min_periods=14).mean().reindex(d.index)
ema = c.loc[c.first_valid_index():].ewm(span=21, adjust=False, min_periods=21).mean().reindex(d.index)
ext = (c - ema) / atr
X = (ext >= 2.0).where(ext.notna())

# ---- Signal Q: Flucht aus High Beta
ratio = p["SPHB_Close"] / p["SPHQ_Close"]
lo, hi = ratio.rolling(84).min(), ratio.rolling(84).max()
rank = 100 * (ratio - lo) / (hi - lo)
Q = ((rank <= 20) & (rank.rolling(10).max() >= 90)).where(rank.rolling(10).max().notna())

# ---- Zielgroesse wie level_steckbriefe.flag(45, .05)
px = d["spy"].to_numpy()
n = len(px)
y = np.full(n, np.nan)
for i in range(n - 1):
    w = px[i + 1:i + 46]
    dip = np.nanmin(w) / px[i] - 1.0
    if dip <= -0.05:
        y[i] = 1.0
    elif len(w) == 45:
        y[i] = 0.0
Y = pd.Series(y, index=d.index)
gate = (d["gate"] == True)                                    # noqa: E712
lvl = d["level_v10"]


def rate(mask: pd.Series) -> dict:
    v = Y[mask.fillna(False) & Y.notna()]
    return {"n": int(len(v)), "k": int(v.sum()), "quote": None if len(v) == 0 else round(float(v.mean()), 4)}


def study(S: pd.Series, name: str) -> dict:
    a = S.first_valid_index()
    per = (d.index >= a)
    res = {"start": str(a.date())}
    g = gate & per & Y.notna() & S.notna()
    res["basis_gate"] = rate(g)
    res["zustand_gate"] = rate(g & (S == True))                # noqa: E712
    yy = Y[g].to_numpy()
    st = (S[g] == True).to_numpy()                             # noqa: E712
    obs, pval, k = shift_test(yy, st)
    res["shift_p"] = round(pval, 4)
    sg = ((S == True) & gate).fillna(False)                    # noqa: E712
    ev = sg & ~(sg.shift(1).rolling(20).max().fillna(0).astype(bool))
    res["ereignis"] = rate(ev & per)
    yrs = (d.index[-1] - a).days / 365.25
    res["ereignis_pro_jahr"] = round(int((ev & per).sum()) / yrs, 2)
    mid = a + (d.index[-1] - a) / 2
    for lab, m in (("haelfte1", d.index < mid), ("haelfte2", d.index >= mid)):
        res[lab] = {"bis" if lab == "haelfte1" else "ab": str(mid.date()),
                    "basis": rate(g & m), "zustand": rate(g & m & (S == True))}  # noqa: E712
    allm = per & Y.notna() & S.notna()
    res["alle_tage"] = {"basis": rate(pd.Series(allm, index=d.index)),
                        "zustand": rate(pd.Series(allm, index=d.index) & (S == True))}  # noqa: E712
    res["anteil_im_warnzustand"] = round(float(((lvl >= 3) & sg).sum() / max(1, sg.sum())), 4)
    res["letzte_signale"] = [f"{t.date()} gate={bool(gate[t])} lvl={lvl[t]}" for t in S.index[(S == True)][-12:]]  # noqa: E712
    return res


def level_frage(extra: pd.Series, name: str) -> dict:
    a = extra.first_valid_index()
    g = gate & (d.index >= a) & Y.notna() & extra.notna() & lvl.notna()
    new = lvl + extra
    out = {"start": str(a.date()), "basis": rate(g),
           "alt_ab3": rate(g & (lvl >= 3)), "neu_ab3": rate(g & (new >= 3)),
           "hinzugekommen": rate(g & (new >= 3) & (lvl < 3)),
           "alt_ab4": rate(g & (lvl >= 4)), "neu_ab4": rate(g & (new >= 4))}
    mid = a + (d.index[-1] - a) / 2
    out["hinzugekommen_h1"] = rate(g & (new >= 3) & (lvl < 3) & (d.index < mid))
    out["hinzugekommen_h2"] = rate(g & (new >= 3) & (lvl < 3) & (d.index >= mid))
    out["basis_h1"], out["basis_h2"] = rate(g & (d.index < mid)), rate(g & (d.index >= mid))
    for k in range(0, 7):
        r = rate(g & (new == k))
        if r["n"]:
            out[f"neu_{k}"] = r
    return out


Xf, Qf = X.astype(float), Q.astype(float)
res = {"X": study(X, "X"), "Q": study(Q, "Q"),
       "level_plus_X": level_frage(Xf, "X"),
       "level_plus_Q": level_frage(Qf, "Q"),
       "level_plus_X_Q": level_frage((Xf + Qf).where(Xf.notna() & Qf.notna()), "XQ")}
rec = pd.DataFrame({"ext": ext.round(2), "X": X, "rank": rank.round(1), "Q": Q, "gate": gate, "lvl": lvl}).loc["2026-08-15":]
res["verlauf_2026"] = {str(t.date()): f"ext={r.ext} X={r.X} rank={r['rank']} Q={r.Q} gate={r.gate} lvl={r.lvl}"
                       for t, r in rec.iterrows() if (r.X == True) or (r.Q == True)}  # noqa: E712
(data / "results_post_signale.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
pd.DataFrame({"ext": ext, "X": X, "rank": rank, "Q": Q}).to_csv(data / "post_signale.csv")
print(json.dumps(res, indent=1, ensure_ascii=False))
print(rec.tail(40).to_string())
