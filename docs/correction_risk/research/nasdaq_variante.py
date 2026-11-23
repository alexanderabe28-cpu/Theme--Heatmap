"""NASDAQ-Variante nach NASDAQ_VARIANTE.md. Aufruf: python nasdaq_variante.py <datenordner>
Gate auf QQQ, Bestaetigungen C/B/R/V unveraendert, Ziel auf QQQ. Ein Lauf, nichts wird angepasst."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import crlib as L

END = "2026-11-20"
data = Path(sys.argv[1])
px = pd.read_csv(data / "prices_all.csv", index_col=0, parse_dates=True)
ex = pd.read_csv(data / "prices_extra.csv", index_col=0, parse_dates=True)
d = L.build(px)                                   # Bestaetigungen und n4 wie im 26-Jahre-Lauf
q = ex["QQQ"].reindex(d.index)
hi = q.rolling(252).max()
d["qqq"] = q
d["gateN"] = (q >= 0.97 * hi).where(hi.notna())
d["distN"] = q / hi - 1.0
ok = d["n4"].notna() & d["gateN"].notna()
d["levelN"] = (d["n4"] * d["gateN"].astype(float)).where(ok)

# Zielgroessen auf QQQ, Zensierung wie in correction_risk.add_outcomes
qa = q.to_numpy()
n = len(qa)
dip = np.full(n, np.nan)
full = np.zeros(n, dtype=bool)
for i in range(n - 1):
    w = qa[i + 1:i + 46]
    if np.isnan(qa[i]) or np.isnan(w).all():
        continue
    dip[i] = np.nanmin(w) / qa[i] - 1.0
    full[i] = len(w) == 45
for name, thr in (("y5", 0.05), ("y8", 0.08)):
    hit = dip <= -thr
    d[name] = np.where(full | hit, hit.astype(float), np.nan)
    d.loc[np.isnan(dip), name] = np.nan

START = str(d.index[ok.to_numpy()][0].date())
W = d.loc[START:END]
W = W[ok.loc[START:END]]
out = {"von": START, "bis": END, "tage": int(len(W)), "jahre": round((W.index[-1] - W.index[0]).days / 365.25, 1)}
print(f"Fenster {START} bis {END}: {len(W)} Handelstage, {out['jahre']} Jahre")


def block(G: pd.DataFrame, ycol: str) -> dict:
    y = G[ycol].to_numpy()
    lvl = G["levelN"].to_numpy()
    r = {"gate_tage": int(len(G)), "basis": float(y.mean()), "je_level": []}
    for k in range(5):
        m = lvl == k
        r["je_level"].append({"level": k, "tage": int(m.sum()), "treffer": int(y[m].sum()),
                              "quote": float(y[m].mean()) if m.any() else None})
    obs, p, nn = L.shift_test(y, lvl >= 3)
    obs2, p2, n2 = L.shift_test(y, lvl >= 2)
    r["warn"] = {"tage": nn, "treffer": int(y[lvl >= 3].sum()), "quote": obs, "p_shift": p}
    r["zwei"] = {"tage": n2, "treffer": int(y[lvl >= 2].sum()), "quote": obs2, "p_shift": p2}
    return r


def show(tag: str, r: dict) -> None:
    lv = " / ".join(f"{x['quote']:.1%} ({x['tage']})" if x["quote"] is not None else "–" for x in r["je_level"])
    print(f"  {tag}: Gate-Tage {r['gate_tage']}, Basis {r['basis']:.1%} | Level 0-4: {lv}")
    print(f"      Warnzustand {r['warn']['tage']} Tage, {r['warn']['quote']:.1%}, Shift-p {r['warn']['p_shift']:.4f}"
          f" | >=2: {r['zwei']['tage']} Tage, {r['zwei']['quote']:.1%}, p {r['zwei']['p_shift']:.4f}")


# ---------------------------------------------------------------- 1 und 2
out["gate_anteil"] = float((W["gateN"] == True).mean())   # noqa: E712
print(f"Gate N an {out['gate_anteil']:.1%} der Tage")
for ycol, label in (("y5", "Ziel 5 %"), ("y8", "Ziel 8 %")):
    G = W[(W["gateN"] == True) & W[ycol].notna()]          # noqa: E712
    out[ycol] = {"gesamt": block(G, ycol)}
    print(f"\n[{label}]")
    show("gesamt", out[ycol]["gesamt"])
    for era, a, b in (("bis 2007", START, "2007-06-19"), ("2007–2016", "2007-06-20", "2016-12-30"), ("ab 2017", "2017-01-03", END)):
        Ge = G.loc[a:b]
        out[ycol][era] = block(Ge, ycol)
        show(era, out[ycol][era])

# ---------------------------------------------------------------- 3
G = W[(W["gateN"] == True) & W["y5"].notna()]              # noqa: E712
out["jahre"] = []
print("\n[Jahre, Ziel 5 %]  Jahr  Gate  Basis  Warn  Treffer")
for yr, g in G.groupby(G.index.year):
    w = g[g["levelN"] >= 3]
    out["jahre"].append({"jahr": int(yr), "gate_tage": int(len(g)), "basis": float(g["y5"].mean()),
                         "warn_tage": int(len(w)), "warn_treffer": int(w["y5"].sum())})
    if len(w):
        print(f"  {yr}  {len(g):4d}  {g['y5'].mean():5.1%}  {len(w):4d}  {int(w['y5'].sum()):4d}")

# ---------------------------------------------------------------- 4
idx = d.index
hi_a = hi.to_numpy()
is_high = qa >= hi_a - 1e-9
i0, i1 = idx.get_loc(pd.Timestamp(START)), idx.get_loc(pd.Timestamp(END))
events, peak, cur = [], None, None
for i in range(i0, i1 + 1):
    if is_high[i]:
        if cur is not None:
            cur["ende"] = i - 1
            events.append(cur); cur = None
        peak = i
    elif peak is not None and cur is None and qa[i] <= 0.95 * qa[peak]:
        cur = {"T": peak, "F": i}
if cur is not None:
    cur["ende"] = i1; cur["offen"] = True
    events.append(cur)
gate = (d["gateN"] == True).fillna(False).to_numpy()      # noqa: E712
warn = gate & (d["levelN"] >= 3).fillna(False).to_numpy()
two = gate & (d["levelN"] >= 2).fillna(False).to_numpy()


def recall(mask: np.ndarray) -> int:
    return sum(1 for e in events if mask[max(e["T"] - 20, 0):e["F"]].any())


def before_top(mask: np.ndarray) -> int:
    return sum(1 for e in events if mask[max(e["T"] - 20, 0):e["T"] + 1].any())


gi = np.where(gate[i0:i1 + 1])[0] + i0
t4 = {"n": len(events), "ab10": int(sum(1 for e in events if qa[e["F"]:e["ende"] + 1].min() / qa[e["T"]] - 1 <= -0.10))}
for name, mask in (("ab3", warn), ("ab2", two)):
    obs = recall(mask)
    sub = mask[gi]
    r_ = []
    for off in range(60, len(gi) - 60 + 1):
        fullm = np.zeros(len(mask), dtype=bool)
        fullm[gi] = np.roll(sub, off)
        r_.append(recall(fullm))
    r_ = np.array(r_)
    t4[name] = {"gewarnt": obs, "zufall_mittel": float(r_.mean()), "q05": float(np.quantile(r_, .05)),
                "q95": float(np.quantile(r_, .95)), "p": float((np.sum(r_ >= obs) + 1) / (len(r_) + 1)),
                "bis_hoch": before_top(mask)}
    print(f"\n[Korrekturen] {name}: gewarnt {obs}/{len(events)} | Zufall nahe Hoch {r_.mean():.1f} "
          f"(5-95 %: {np.quantile(r_, .05):.0f}-{np.quantile(r_, .95):.0f}), p {t4[name]['p']:.4f} | bis zum Hoch-Tag: {t4[name]['bis_hoch']}")
t4["liste"] = [{"hoch": str(idx[e["T"]].date()), "minus5": str(idx[e["F"]].date()),
                "tiefe": float(qa[e["F"]:e["ende"] + 1].min() / qa[e["T"]] - 1),
                "gewarnt": bool(warn[max(e["T"] - 20, 0):e["F"]].any()), "offen": bool(e.get("offen", False))} for e in events]
print(f"  Korrekturen >= 5 %: {t4['n']}, davon >= 10 %: {t4['ab10']}")
print("  nicht gewarnt, >= 10 %:", [(x["hoch"], round(x["tiefe"], 3)) for x in t4["liste"] if not x["gewarnt"] and x["tiefe"] <= -0.10])
out["korrekturen"] = t4

# Stand heute, beide Indizes
last = d.loc[:END].iloc[-1]
out["stand"] = {"datum": END, "n4": int(last["n4"]), "C": bool(last["C"]), "B": bool(last["B"]), "R": bool(last["R"]), "V": bool(last["V"]),
                "gate_spx": bool(last["gate"]), "dist_spx": float(last["dist_high"]),
                "gate_ndq": bool(last["gateN"]), "dist_ndq": float(last["distN"])}
print("\nStand:", out["stand"])
(data / "results_nasdaq.json").write_text(json.dumps(out, indent=1))
d[["spy", "qqq", "gate", "gateN", "dist_high", "distN", "C", "B", "R", "V", "n4", "level_v10", "levelN"]].to_csv(data / "levels_py.csv")
print("geschrieben: results_nasdaq.json, levels_py.csv")
