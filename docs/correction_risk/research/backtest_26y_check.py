"""Nachtrag und unabhaengige Nachrechnung zum 26-Jahre-Lauf. Aufruf: python backtest_26y_check.py <datenordner>
(1) strengerer Zufallsvergleich nur ueber Tage nahe Hoch, (2) woher der O1-Effekt kommt, (3) Overlay neu gerechnet."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import crlib as L

START, END = "2000-01-03", "2026-11-20"
data = Path(sys.argv[1])
px = pd.read_csv(data / "prices_all.csv", index_col=0, parse_dates=True)
ex = pd.read_csv(data / "prices_extra.csv", index_col=0, parse_dates=True)
res = json.loads((data / "results_26y.json").read_text())
d = L.build(px)
gate = (d["gate"] == True).fillna(False).to_numpy()            # noqa: E712
warn = (gate & (d["level_v10"] >= 3).fillna(False).to_numpy())
two = (gate & (d["level_v10"] >= 2).fillna(False).to_numpy())
idx = d.index
i0, i1 = idx.get_loc(pd.Timestamp(START)), idx.get_loc(pd.Timestamp(END))
ev = [(idx.get_loc(pd.Timestamp(x["hoch"])), idx.get_loc(pd.Timestamp(x["minus5"]))) for x in res["teil2"]["liste"]]
nach = {}


def recall(mask):
    return sum(1 for T, F in ev if mask[max(T - 20, 0):F].any())


def before_top(mask):
    return sum(1 for T, F in ev if mask[max(T - 20, 0):T + 1].any())


# (1) Zufallsvergleich nur ueber Gate-Tage: Warnreihe innerhalb der Gate-Tag-Folge zirkulaer verschieben
gi = np.where(gate[i0:i1 + 1])[0] + i0
for name, mask in (("ab3", warn), ("ab2", two)):
    sub = mask[gi]
    obs = recall(mask)
    r_ = []
    for off in range(60, len(gi) - 60 + 1):
        full = np.zeros(len(mask), dtype=bool)
        full[gi] = np.roll(sub, off)
        r_.append(recall(full))
    r_ = np.array(r_)
    nach[f"zufall_gate_{name}"] = {"beobachtet": obs, "mittel": float(r_.mean()), "q05": float(np.quantile(r_, .05)),
                                   "q95": float(np.quantile(r_, .95)), "p": float((np.sum(r_ >= obs) + 1) / (len(r_) + 1))}
    print(f"Erkennung {name}: {obs}/{len(ev)} | Zufall nur nahe Hoch: Mittel {r_.mean():.1f} (5-95 %: {np.quantile(r_, .05):.0f}-"
          f"{np.quantile(r_, .95):.0f}), p {nach[f'zufall_gate_{name}']['p']:.4f}")
nach["vor_dem_hoch_ab3"] = before_top(warn); nach["vor_dem_hoch_ab2"] = before_top(two)
leads = [x["vorlauf_ab3"] for x in res["teil2"]["liste"] if x["vorlauf_ab3"] is not None]
nach["vorlauf_ab10_sessions"] = int(sum(1 for v in leads if v >= 10))
print(f"Warnzustand schon bis zum Hoch-Tag: {nach['vor_dem_hoch_ab3']}/{len(ev)} | Vorlauf >= 10 Sessions: {nach['vorlauf_ab10_sessions']}/{len(leads)}")

# (3) Overlay unabhaengig nachgerechnet (pandas, andere Formulierung)
spy = d["spy"]
r = spy.pct_change()
cash = (ex["^IRX"].reindex(idx).ffill() / 100 / 252).shift(1)
w = pd.Series(warn, index=idx)
out1 = w.shift(2, fill_value=False)
out2 = pd.concat([w.shift(k, fill_value=False) for k in range(2, 47)], axis=1).any(axis=1)


def stats(ret):
    ret = ret.loc[START:END]
    eq = (1 + ret).cumprod()
    yrs = (ret.index[-1] - ret.index[0]).days / 365.25
    return eq.iloc[-1] ** (1 / yrs) - 1, (eq / eq.cummax() - 1).min()


for name, o in (("B0", pd.Series(False, index=idx)), ("O1", out1), ("O2", out2)):
    c, dd = stats(r.where(~o, cash))
    ref = res["teil3"]["regeln"][name]
    print(f"Nachrechnung {name}: {c:.4%} / {dd:.2%} | Hauptlauf {ref['rendite_pa']:.4%} / {ref['max_dd']:.2%}")
    assert abs(c - ref["rendite_pa"]) < 1e-9 and abs(dd - ref["max_dd"]) < 1e-9

# (2) Woher kommt der O1-Effekt?
rw = r.loc[START:END]; o1 = out1.loc[START:END]; cw = cash.loc[START:END]
days = rw[o1]
nach["o1"] = {"tage": int(o1.sum()), "mittel_tagesrendite": float(days.mean()), "median": float(days.median()),
              "anteil_negativ": float((days < 0).mean()), "mittel_alle_tage": float(rw.mean()),
              "summe_log": float(np.log1p(days).sum())}
print(f"\nO1-Kassentage: {int(o1.sum())}, mittlere SPY-Tagesrendite {days.mean():+.3%} (alle Tage {rw.mean():+.3%}), "
      f"Median {days.median():+.3%}, Anteil negativ {(days < 0).mean():.1%}, Summe log {np.log1p(days).sum():+.1%}")
worst = days.nsmallest(8)
print("groesste vermiedene Verlusttage:", [(str(k.date()), round(float(v) * 100, 2)) for k, v in worst.items()])
nach["o1"]["top_tage"] = [[str(k.date()), float(v)] for k, v in worst.items()]
ex5 = o1.copy(); ex5[worst.index[:5]] = False
c5, _ = stats(rw.where(~ex5, cw)); cb, _ = stats(rw)
nach["o1"]["rendite_ohne_top5"] = float(c5); nach["o1"]["vorsprung_ohne_top5"] = float(c5 - cb)
print(f"O1 ohne die 5 groessten vermiedenen Verlusttage: {c5:.2%} p.a. (Buy and Hold {cb:.2%})")
by = pd.DataFrame({"spy": np.log1p(rw), "o1": np.log1p(rw.where(~o1, cw))}).groupby(rw.index.year).sum()
by["diff"] = by["o1"] - by["spy"]
nach["o1"]["jahre_besser"] = int((by["diff"] > 1e-9).sum()); nach["o1"]["jahre_schlechter"] = int((by["diff"] < -1e-9).sum())
nach["o1"]["jahre"] = {int(k): float(v) for k, v in by["diff"].items()}
print("O1 minus Buy and Hold je Jahr (log, Prozentpunkte):", {int(k): round(float(v) * 100, 1) for k, v in by["diff"].items() if abs(v) > 1e-9})
print(f"Jahre besser {nach['o1']['jahre_besser']}, schlechter {nach['o1']['jahre_schlechter']}")
# Zufallsvergleich O1 nur ueber Gate-Tage (Kassentage innerhalb der Gate-Tag-Folge verschoben, dann 2 Tage Verzoegerung)
ra, ca = rw.to_numpy(), cw.to_numpy()
yrs = (rw.index[-1] - rw.index[0]).days / 365.25
obs_c = res["teil3"]["regeln"]["O1"]["rendite_pa"]
sub = warn[gi]; cg = []
for off in range(60, len(gi) - 60 + 1):
    full = np.zeros(len(warn), dtype=bool); full[gi] = np.roll(sub, off)
    m = np.roll(full, 2)[i0:i1 + 1]
    cg.append(np.prod(1 + np.where(m, ca, ra)) ** (1 / yrs) - 1)
cg = np.array(cg)
nach["o1"]["zufall_gate"] = {"mittel": float(cg.mean()), "p": float((np.sum(cg >= obs_c) + 1) / (len(cg) + 1))}
print(f"O1 Zufall nur nahe Hoch: Rendite im Mittel {cg.mean():.2%}, p {nach['o1']['zufall_gate']['p']:.4f}")
# Verzoegerung 0..5 Tage (nachtraeglich, beschreibend)
lag = {}
for k in range(0, 6):
    c, _ = stats(r.where(~w.shift(k + 1, fill_value=False), cash))
    lag[k] = float(c)
nach["o1"]["verzoegerung"] = lag
print("O1 Rendite p.a. nach Verzoegerung in Tagen:", {k: f"{v:.2%}" for k, v in lag.items()})
res["nachtrag"] = nach
(data / "results_26y.json").write_text(json.dumps(res, indent=1, default=float))
