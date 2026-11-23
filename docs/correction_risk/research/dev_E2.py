"""Nachtrag Entwicklung, weiterhin NUR E: gewichtete Varianten und der reine Zaehler. Aufruf: python dev_E2.py <datenordner>"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
import crlib as L

data = Path(sys.argv[1])
d = L.build(pd.read_csv(data / "prices_all.csv", index_col=0, parse_dates=True))
E = L.segment(d, "E")
assert E.index.max() <= pd.Timestamp(L.E_END)
y = E["y45"].to_numpy()
E = E.assign(n2=E[["C", "B"]].astype(float).sum(axis=1))
for c in L.COMPS7:
    E[c + "_f"] = E[c].astype(float)
CAND = {
    "M0 Konstante": [],
    "Zaehler n4": ["n4"],
    "M3 logVIX+n4": ["logvix", "n4"],
    "nSel (verschachtelt)": ["nSel"],
    "K4 vier Gewichte": [c + "_f" for c in L.COMPS4],
    "K5 sieben Gewichte": [c + "_f" for c in L.COMPS7],
    "K2 C+B (nachtraeglich)": ["n2"],
}
folds = []
for yr in sorted(set(E.index.year)):
    te = E[E.index.year == yr]
    if len(te) < 20:
        continue
    tr = E[(E["pos"] < te["pos"].min() - 45) | (E["pos"] > te["pos"].max() + 45)]
    folds.append((yr, tr, te))
res = {k: {"ll": [], "auc": []} for k in CAND}
for yr, tr, te in folds:
    comps = L.select_comps(tr)
    trx, tex = L.with_nsel(tr, comps), L.with_nsel(te, comps)
    ytr, yte = trx["y45"].to_numpy(), tex["y45"].to_numpy()
    for k, feats in CAND.items():
        if feats:
            w = L.fit_logit(trx[feats].to_numpy(float), ytr)
            p = L.predict(w, tex[feats].to_numpy(float))
        else:
            p = np.full(len(yte), ytr.mean())
        res[k]["ll"].append(L.logloss(yte, p))
        a = L.auc(yte, p) if feats else 0.5
        if not np.isnan(a):
            res[k]["auc"].append(a)
ref = np.array(res["Zaehler n4"]["ll"])
print(f"{'Kandidat':26s} CV-LogLoss  Diff zu n4   mittl. Fold-AUC")
for k in CAND:
    ll = np.array(res[k]["ll"])
    print(f"{k:26s} {ll.mean():.4f}     {ll.mean()-ref.mean():+.4f}      {np.mean(res[k]['auc']):.3f}")

print("\nGewichte K4 / K5 auf ganz E (Log-Odds):")
for name in ("K4 vier Gewichte", "K5 sieben Gewichte"):
    w = L.fit_logit(E[CAND[name]].to_numpy(float), y)
    print(" ", name, dict(zip(["const"] + [f[0] for f in CAND[name]], np.round(w, 2))))

w = L.fit_logit(E[["n4"]].to_numpy(float), y)
print("\nZaehler n4 auf E: Konstante %.4f, Steigung %.4f" % (w[0], w[1]))
p = L.predict(w, E[["n4"]].to_numpy(float))
print("In-Sample AUC %.3f, Brier %.4f gegen Konstante %.4f" % (L.auc(y, p), L.brier(y, p), L.brier(y, np.full(len(y), y.mean()))))
for k in range(5):
    m = (E["n4"] == k).to_numpy()
    print(f"  n4={k}: {m.sum()} Tage, geschaetzt {p[m].mean():.1%}, eingetreten {y[m].mean():.1%}")
