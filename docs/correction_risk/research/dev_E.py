"""Entwicklung nach Protokoll v1.1: NUR Stichprobe E (2007-2016). Aufruf: python dev_E.py <datenordner>"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import crlib as L

data = Path(sys.argv[1])
px = pd.read_csv(data / "prices_all.csv", index_col=0, parse_dates=True)
d = L.build(px)
E = L.segment(d, "E")
Eall = L.all_days(d, "E")
assert E.index.max() <= pd.Timestamp(L.E_END) and Eall.index.max() <= pd.Timestamp(L.E_END)
y = E["y45"].to_numpy()
base = y.mean()
print(f"E: {E.index[0].date()} bis {E.index[-1].date()}, Gate-Tage {len(E)}, Basisrate {base:.1%}")

print("\n[1] Komponenten einzeln (Tagesebene, Gate-Tage E)")
for c in L.COMPS7:
    st = (E[c] == True).to_numpy()
    obs, p, k = L.shift_test(y, st)
    print(f"  {c}: wahr an {k} Tagen ({k/len(E):.1%}), Quote {obs:.1%}, Lift {obs/base:.2f}, Shift-p {p:.3f}")

print("\n[2] v1.0 Zaehl-Level: Zustand (Tagesebene) und Erstsignal (Episodenstart)")
for k in (1, 2, 3, 4):
    st = (E["level_v10"] >= k).to_numpy()
    obs, p, n = L.shift_test(y, st)
    ep = L.cr.episode_starts(d[d["valid"]]["level_v10"], k).reindex(Eall.index).fillna(False)
    e = Eall[ep.to_numpy() & Eall["y45"].notna().to_numpy()]
    print(f"  Level>={k}: Zustand {n} Tage Quote {obs:.1%} p={p:.3f} | Erstsignal {int(e['y45'].sum())}/{len(e)}"
          f" = {e['y45'].mean():.1%}")
    if k in (2, 3):
        thr = np.sort(E["vix"].to_numpy())[::-1][n - 1]
        vb = (E["vix"] >= thr).to_numpy()
        o2, p2, n2 = L.shift_test(y, vb)
        print(f"     VIX-Benchmark gleicher Haeufigkeit (VIX >= {thr:.1f}): {n2} Tage Quote {o2:.1%} p={p2:.3f}")

print("\n[3] Quote nach VIX-Quintil (Gate-Tage E)")
q = pd.qcut(E["vix"], 5)
print(E.groupby(q, observed=True)["y45"].agg(["count", "mean"]).round(3).to_string())

print("\n[4] Kreuzvalidierung (Leave-one-year-out, gepaarte 1-SE-Regel)")
years = sorted(set(E.index.year))
folds = []
for yr in years:
    te = E[E.index.year == yr]
    if len(te) < 20:
        print(f"  Jahr {yr}: {len(te)} Gate-Tage, kein Fold")
        continue
    tr = E[(E["pos"] < te["pos"].min() - 45) | (E["pos"] > te["pos"].max() + 45)]
    folds.append((yr, tr, te))
names = list(L.MODELS) + ["M0", "v1.0-Score"]
loss = {m: [] for m in names}
for yr, tr, te in folds:
    comps = L.select_comps(tr)
    trx, tex = L.with_nsel(tr, comps), L.with_nsel(te, comps)
    ytr, yte = trx["y45"].to_numpy(), tex["y45"].to_numpy()
    for m, feats in L.MODELS.items():
        w = L.fit_logit(trx[feats].to_numpy(float), ytr)
        loss[m].append(L.logloss(yte, L.predict(w, tex[feats].to_numpy(float))))
    loss["M0"].append(L.logloss(yte, np.full(len(yte), ytr.mean())))
    w = L.fit_logit(trx[["n4"]].to_numpy(float), ytr)
    loss["v1.0-Score"].append(L.logloss(yte, L.predict(w, tex[["n4"]].to_numpy(float))))
    print(f"  Fold {yr}: Test {len(te)} Tage, Basisrate {yte.mean():.1%}, nSel-Komponenten {comps}")
Lm = {m: np.array(v) for m, v in loss.items()}
means = {m: Lm[m].mean() for m in names}
best = min(L.MODELS, key=lambda m: means[m])
F = len(folds)
print(f"\n  {'Modell':11s} {'Merkmale':28s} LogLoss   Diff zu best  SE     gleichwertig")
equiv = []
for m in names:
    diff = Lm[m] - Lm[best]
    se = diff.std(ddof=1) / np.sqrt(F) if m != best else 0.0
    eq = diff.mean() <= se + 1e-12
    feats = "+".join(L.MODELS.get(m, ["-"] if m == "M0" else ["n4"]))
    print(f"  {m:11s} {feats:28s} {means[m]:.4f}   {diff.mean():+.4f}      {se:.4f} {'ja' if eq else 'nein'}")
    if eq and m in L.MODELS:
        equiv.append(m)
chosen = sorted(equiv, key=lambda m: (len(L.MODELS[m]), means[m]))[0]
print(f"\n  Bestes Modell nach Log-Loss: {best}. Gewaehlt nach 1-SE-Regel: {chosen} ({'+'.join(L.MODELS[chosen])})")

print("\n[5] Einfrieren")
comps_all = L.select_comps(E)
Ex = L.with_nsel(E, comps_all)
feats = L.MODELS[chosen]
w = L.fit_logit(Ex[feats].to_numpy(float), y)
p = L.predict(w, Ex[feats].to_numpy(float))
cuts = [float(np.quantile(p, qq)) for qq in (0.50, 0.75, 0.90, 0.97)]
lv = L.levels_from_p(p, cuts)
print("  Koeffizienten (Konstante, " + ", ".join(feats) + "):", np.round(w, 4).tolist())
print("  Grenzen p:", [round(c, 4) for c in cuts], "| nSel-Komponenten auf E:", comps_all)
print(f"  In-Sample: AUC {L.auc(y, p):.3f}, Brier {L.brier(y, p):.4f} gegen Konstante {L.brier(y, np.full(len(y), base)):.4f}")
for k in range(5):
    m = lv == k
    print(f"  Level {k}: {m.sum()} Tage, geschaetzt {p[m].mean():.1%}, eingetreten {y[m].mean():.1%}")
w1 = L.fit_logit(E[["logvix"]].to_numpy(float), y)
frozen = {"version": "1.1", "modell": chosen, "merkmale": feats, "koeffizienten": w.tolist(), "grenzen": cuts,
          "nsel_komponenten": comps_all, "m1_koeffizienten": w1.tolist(), "E_basisrate": float(base),
          "E_von": str(E.index[0].date()), "E_bis": str(E.index[-1].date()), "E_gate_tage": int(len(E)),
          "cv_logloss": {m: float(means[m]) for m in names}, "cv_bestes": best}
(data / "spec_v11_frozen.json").write_text(json.dumps(frozen, indent=1))
print("  gespeichert: spec_v11_frozen.json")
