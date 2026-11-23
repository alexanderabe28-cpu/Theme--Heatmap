"""Grosser Backtest 2000-2026 nach BACKTEST_26J.md. Aufruf: python backtest_26y.py <datenordner>
Modell: eingefrorenes v1.1 (Warnzustand = Gate an und >= 3 von 4 Bestaetigungen). Nichts wird angepasst."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import crlib as L

START, END = "2000-01-03", "2026-11-20"
data = Path(sys.argv[1])
px = pd.read_csv(data / "prices_all.csv", index_col=0, parse_dates=True)
ex = pd.read_csv(data / "prices_extra.csv", index_col=0, parse_dates=True)
d = L.build(px)
d["warn"] = ((d["gate"] == True) & (d["level_v10"] >= 3)).fillna(False)   # noqa: E712
d["two"] = ((d["gate"] == True) & (d["level_v10"] >= 2)).fillna(False)    # noqa: E712
W = d.loc[START:END]
assert W["valid"].all(), "Fenster enthaelt ungueltige Tage"
N = len(W)
out = {"von": START, "bis": END, "jahre": round((W.index[-1] - W.index[0]).days / 365.25, 1), "tage": N}
print(f"Fenster {START} bis {END}: {N} Handelstage, {out['jahre']} Jahre")

# ---------------------------------------------------------------- Teil 1
G = W[(W["gate"] == True) & W["y45"].notna()]   # noqa: E712
y = G["y45"].to_numpy()
base = y.mean()
lvl = G["level_v10"].to_numpy()
t1 = {"gate_tage": int(len(G)), "gate_anteil": float((W["gate"] == True).mean()), "basis": float(base), "je_level": []}  # noqa: E712
print(f"\n[Teil 1] Gate-Tage {len(G)} ({t1['gate_anteil']:.1%} aller Tage), Basisrate {base:.1%}")
for k in range(5):
    m = lvl == k
    t1["je_level"].append({"level": k, "tage": int(m.sum()), "treffer": int(y[m].sum())})
    print(f"  Level {k}: {m.sum():4d} Tage, {y[m].mean():.1%}")
obs, p, n = L.shift_test(y, lvl >= 3)
obs2, p2, n2 = L.shift_test(y, lvl >= 2)
t1["warn"] = {"tage": n, "treffer": int(y[lvl >= 3].sum()), "quote": obs, "p_shift": p}
t1["zwei"] = {"tage": n2, "treffer": int(y[lvl >= 2].sum()), "quote": obs2, "p_shift": p2}
print(f"  Warnzustand (>=3): {n} Tage, {obs:.1%}, Shift-p {p:.4f} | >=2: {n2} Tage, {obs2:.1%}, p {p2:.4f}")
ep = L.cr.episode_starts(d[d["valid"]]["level_v10"], 3).reindex(W.index).fillna(False)
e = W[ep.to_numpy() & W["y45"].notna().to_numpy()]
t1["erstsignal_ab3"] = [int(e["y45"].sum()), int(len(e))]
print(f"  Erstsignal Level>=3: {int(e['y45'].sum())}/{len(e)}")
t1["jahre"] = []
print("  Jahr  Gate  Basis   Warn  Treffer")
for yr, g in G.groupby(G.index.year):
    w = g[g["level_v10"] >= 3]
    row = {"jahr": int(yr), "gate_tage": int(len(g)), "basis": float(g["y45"].mean()),
           "warn_tage": int(len(w)), "warn_treffer": int(w["y45"].sum())}
    t1["jahre"].append(row)
    print(f"  {yr}  {len(g):4d}  {g['y45'].mean():5.1%}  {len(w):4d}  {int(w['y45'].sum()):4d}")
# QQQ als Ziel (Nebenbefund)
q = ex["QQQ"].reindex(d.index)
qa = q.to_numpy()
dipq = np.full(len(q), np.nan)
for i in range(len(q) - 45):
    w_ = qa[i + 1:i + 46]
    if not np.isnan(qa[i]) and not np.isnan(w_).any():
        dipq[i] = w_.min() / qa[i] - 1
d["dipq"] = dipq
Gq = d.loc[START:END]
Gq = Gq[(Gq["gate"] == True) & Gq["dipq"].notna()]   # noqa: E712
wq = Gq[Gq["level_v10"] >= 3]
t1["qqq"] = {"gate_tage": int(len(Gq)), "warn_tage": int(len(wq)),
             "q5_gate": float((Gq["dipq"] <= -0.05).mean()), "q5_warn": float((wq["dipq"] <= -0.05).mean()),
             "q8_gate": float((Gq["dipq"] <= -0.08).mean()), "q8_warn": float((wq["dipq"] <= -0.08).mean()),
             "dip_gate": float(Gq["dipq"].median()), "dip_warn": float(wq["dipq"].median())}
print("  QQQ als Ziel:", {k: round(v, 3) if isinstance(v, float) else v for k, v in t1["qqq"].items()})
out["teil1"] = t1

# ---------------------------------------------------------------- Teil 2
spy = d["spy"].to_numpy()
idx = d.index
hi = d["spy"].rolling(252).max().to_numpy()
is_high = spy >= hi - 1e-9
i_start, i_end = idx.get_loc(pd.Timestamp(START)), idx.get_loc(pd.Timestamp(END))
events, peak, cur = [], None, None
for i in range(252, i_end + 1):
    if is_high[i]:
        if cur is not None:
            cur["ende"] = i - 1
            events.append(cur); cur = None
        peak = i
    elif peak is not None and cur is None and spy[i] <= 0.95 * spy[peak]:
        cur = {"T": peak, "F": i}
if cur is not None:
    cur["ende"] = i_end; cur["offen"] = True
    events.append(cur)
events = [e_ for e_ in events if e_["F"] >= i_start]
warn_all = d["warn"].to_numpy()
two_all = d["two"].to_numpy()


def recall(mask: np.ndarray) -> tuple[int, list]:
    hits, leads = 0, []
    for e_ in events:
        a, b = max(e_["T"] - 20, 0), e_["F"] - 1
        w_ = np.where(mask[a:b + 1])[0]
        if len(w_):
            hits += 1
            leads.append(e_["F"] - (a + w_[0]))
        else:
            leads.append(None)
    return hits, leads


h3, lead3 = recall(warn_all)
h2, lead2 = recall(two_all)
t2 = {"n": len(events), "gewarnt_ab3": h3, "gewarnt_ab2": h2, "liste": []}
for e_, l3, l2 in zip(events, lead3, lead2):
    tr = spy[e_["F"]:e_["ende"] + 1].min()
    t2["liste"].append({"hoch": str(idx[e_["T"]].date()), "minus5": str(idx[e_["F"]].date()),
                        "tiefe": float(tr / spy[e_["T"]] - 1), "tage_bis_minus5": int(e_["F"] - e_["T"]),
                        "vorlauf_ab3": l3, "vorlauf_ab2": l2, "offen": bool(e_.get("offen", False))})
# Zufallsvergleich: Warnreihe zirkulaer im Fenster verschieben
seg = slice(i_start, i_end + 1)


def placebo_recall(mask_all: np.ndarray, obs_hits: int) -> dict:
    m = mask_all[seg].copy()
    res = []
    for off in range(60, N - 60 + 1):
        full = np.zeros(len(mask_all), dtype=bool)
        full[seg] = np.roll(m, off)
        res.append(recall(full)[0])
    res = np.array(res)
    return {"mittel": float(res.mean()), "p": float((np.sum(res >= obs_hits) + 1) / (len(res) + 1)),
            "q05": float(np.quantile(res, 0.05)), "q95": float(np.quantile(res, 0.95))}


t2["zufall_ab3"] = placebo_recall(warn_all, h3)
t2["zufall_ab2"] = placebo_recall(two_all, h2)
big = [x for x in t2["liste"] if x["tiefe"] <= -0.10]
t2["ab10"] = {"n": len(big), "gewarnt_ab3": sum(1 for x in big if x["vorlauf_ab3"] is not None),
              "gewarnt_ab2": sum(1 for x in big if x["vorlauf_ab2"] is not None)}
l3 = [x["vorlauf_ab3"] for x in t2["liste"] if x["vorlauf_ab3"] is not None]
t2["vorlauf_median_ab3"] = float(np.median(l3)) if l3 else None
print(f"\n[Teil 2] Korrekturen ab 252-Tage-Hoch (>=5 %): {len(events)}; davon >=10 %: {len(big)}")
print(f"  gewarnt (Warnzustand): {h3}/{len(events)}, Zufall im Mittel {t2['zufall_ab3']['mittel']:.1f} "
      f"(5-95 %: {t2['zufall_ab3']['q05']:.0f}-{t2['zufall_ab3']['q95']:.0f}), p {t2['zufall_ab3']['p']:.4f}")
print(f"  gewarnt (>=2 Bestaetigungen): {h2}/{len(events)}, Zufall im Mittel {t2['zufall_ab2']['mittel']:.1f}, p {t2['zufall_ab2']['p']:.4f}")
print(f"  >=10 %: Warnzustand {t2['ab10']['gewarnt_ab3']}/{len(big)}, >=2: {t2['ab10']['gewarnt_ab2']}/{len(big)}; "
      f"Median Vorlauf bis -5 %: {t2['vorlauf_median_ab3']} Sessions")
for x in t2["liste"]:
    print(f"   Hoch {x['hoch']} -5% am {x['minus5']} Tiefe {x['tiefe']:.1%} | Warn-Vorlauf {x['vorlauf_ab3']} | >=2: {x['vorlauf_ab2']}"
          + (" (offen)" if x["offen"] else ""))
out["teil2"] = t2

# ---------------------------------------------------------------- Teil 3
r = (d["spy"] / d["spy"].shift(1) - 1).loc[START:END]
irx = ex["^IRX"].reindex(d.index).ffill()
cash = (irx.shift(1) / 100 / 252).loc[START:END]
sma200 = d["spy"].rolling(200).mean()
wf = d["warn"].astype(float)
masks = {
    "O1": (wf.shift(2) > 0), "O2": (wf.rolling(45).max().shift(2) > 0),
    "O1_lag0": (wf.shift(1) > 0), "O2_lag0": (wf.rolling(45).max().shift(1) > 0),
    "B1": ~((d["spy"] > sma200).shift(2).fillna(False).astype(bool)),
}
masks = {k: v.loc[START:END].to_numpy() for k, v in masks.items()}
ra, ca = r.to_numpy(), cash.to_numpy()
years = (r.index[-1] - r.index[0]).days / 365.25


def metrics(ret: np.ndarray, pos: np.ndarray, yrs: float = years, cash_=None) -> dict:
    cash_ = ca if cash_ is None else cash_
    eq = np.cumprod(1 + ret)
    dd = eq / np.maximum.accumulate(eq) - 1
    return {"rendite_pa": float(eq[-1] ** (1 / yrs) - 1), "vola": float(ret.std() * np.sqrt(252)),
            "sharpe": float((ret - cash_).mean() / ret.std() * np.sqrt(252)), "max_dd": float(dd.min()),
            "investiert": float(pos.mean()), "ausstiege": int(np.sum((pos[1:] < 1) & (pos[:-1] == 1))),
            "endwert": float(eq[-1] * 100)}


def strat(mask: np.ndarray, weight_out: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    pos = np.where(mask, weight_out, 1.0)
    return pos * ra + (1 - pos) * ca, pos


rets = {"B0": (ra, np.ones(N))}
rets["O1"] = strat(masks["O1"]); rets["O2"] = strat(masks["O2"]); rets["O3"] = strat(masks["O2"], 0.5)
rets["B1"] = strat(masks["B1"])
rets["O1_lag0"] = strat(masks["O1_lag0"]); rets["O2_lag0"] = strat(masks["O2_lag0"])
t3 = {"regeln": {k: metrics(*v) for k, v in rets.items()}}


def placebo_strat(mask: np.ndarray, obs: dict) -> dict:
    cg, dd = [], []
    for off in range(60, N - 60 + 1):
        m = np.roll(mask, off)
        eq = np.cumprod(1 + np.where(m, ca, ra))
        cg.append(eq[-1] ** (1 / years) - 1)
        dd.append((eq / np.maximum.accumulate(eq) - 1).min())
    cg, dd = np.array(cg), np.array(dd)
    return {"rendite_mittel": float(cg.mean()), "p_rendite": float((np.sum(cg >= obs["rendite_pa"]) + 1) / (len(cg) + 1)),
            "dd_mittel": float(dd.mean()), "p_dd": float((np.sum(dd >= obs["max_dd"]) + 1) / (len(dd) + 1))}


t3["zufall"] = {k: placebo_strat(masks[k], t3["regeln"][k]) for k in ("O1", "O2")}
print("\n[Teil 3] Ausstieg im Warnzustand (Umsetzung einen Tag spaeter)")
print(f"  {'Regel':8s} Rendite p.a.  Vola   Sharpe  MaxDD    investiert  Ausstiege  Endwert(100)")
for k, m in t3["regeln"].items():
    print(f"  {k:8s} {m['rendite_pa']:8.2%}   {m['vola']:6.1%}  {m['sharpe']:5.2f}  {m['max_dd']:7.1%}  {m['investiert']:8.1%}  "
          f"{m['ausstiege']:6d}     {m['endwert']:8.0f}")
for k, z in t3["zufall"].items():
    print(f"  Zufall {k}: Rendite im Mittel {z['rendite_mittel']:.2%} (p {z['p_rendite']:.3f}), MaxDD im Mittel {z['dd_mittel']:.1%} (p {z['p_dd']:.3f})")
t3["teilzeit"] = []
for a, b in (("2000-01-03", "2007-06-19"), ("2007-06-20", "2016-12-30"), ("2017-01-03", END)):
    sl = (r.index >= a) & (r.index <= b)
    yrs = (r.index[sl][-1] - r.index[sl][0]).days / 365.25
    row = {"von": a, "bis": b}
    for k in ("B0", "O2", "O1", "B1"):
        row[k] = metrics(rets[k][0][sl], rets[k][1][sl], yrs, ca[sl])
    t3["teilzeit"].append(row)
    print(f"  {a[:4]}-{b[:4]}: B0 {row['B0']['rendite_pa']:.2%} / {row['B0']['max_dd']:.1%} | O2 {row['O2']['rendite_pa']:.2%} / "
          f"{row['O2']['max_dd']:.1%} | O1 {row['O1']['rendite_pa']:.2%} / {row['O1']['max_dd']:.1%} | B1 {row['B1']['rendite_pa']:.2%} / {row['B1']['max_dd']:.1%}")
eq = pd.DataFrame({k: np.cumprod(1 + rets[k][0]) * 100 for k in ("B0", "O1", "O2", "O3", "B1")}, index=r.index)
me = eq.groupby([eq.index.year, eq.index.month]).tail(1)
t3["kurven"] = {"datum": [str(x.date()) for x in me.index], **{k: [round(float(v), 2) for v in me[k]] for k in me}}
out["teil3"] = t3

# ---------------------------------------------------------------- Teil 4
wd = W[W["warn"]]
runs, cur = [], [wd.index[0]]
for a, b in zip(wd.index[:-1], wd.index[1:]):
    if d.at[b, "pos"] - d.at[a, "pos"] > 10:
        runs.append(cur); cur = []
    cur.append(b)
runs.append(cur)
t4 = []
for rn in runs:
    rr = W.loc[rn]
    i0 = int(d.at[rn[0], "pos"])
    win = spy[i0 + 1:i0 + 46]
    t4.append({"von": str(rn[0].date()), "bis": str(rn[-1].date()), "tage": len(rn), "max_level": int(rr["level_v10"].max()),
               "komponenten": "".join(c for c in L.COMPS4 if (rr[c] == True).any()),   # noqa: E712
               "dip45": float(win.min() / spy[i0] - 1) if len(win) else None, "fenster_voll": bool(len(win) == 45),
               "fwd45": float(spy[i0 + 45] / spy[i0] - 1) if i0 + 45 < len(spy) else None,
               "treffer_erster_tag": None if np.isnan(rr["y45"].iloc[0]) else int(rr["y45"].iloc[0]),
               "treffer_tage": int(rr["y45"].sum()), "spy": float(spy[i0])})
out["teil4"] = t4
hit_runs = sum(1 for x in t4 if x["treffer_erster_tag"] == 1)
known_runs = sum(1 for x in t4 if x["treffer_erster_tag"] is not None)
print(f"\n[Teil 4] {len(t4)} Laeufe im Warnzustand; erster Tag Treffer in {hit_runs}/{known_runs}; "
      f"Median Dauer {np.median([x['tage'] for x in t4]):.0f} Tage")
wk = d["spy"].loc[START:END].resample("W-FRI").last().dropna()
out["spy_woche"] = {"datum": [str(x.date()) for x in wk.index], "schluss": [round(float(v), 2) for v in wk]}
(data / "results_26y.json").write_text(json.dumps(out, indent=1, default=float))
print("gespeichert: results_26y.json")
