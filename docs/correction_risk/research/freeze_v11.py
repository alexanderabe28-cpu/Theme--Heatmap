"""Friert v1.1 ein. Rechnet nur auf E. Aufruf: python freeze_v11.py <datenordner>"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import crlib as L

data = Path(sys.argv[1])
d = L.build(pd.read_csv(data / "prices_all.csv", index_col=0, parse_dates=True))
E = L.segment(d, "E")
assert E.index.max() <= pd.Timestamp(L.E_END)
y = E["y45"].to_numpy()
w = L.fit_logit(E[["n4"]].to_numpy(float), y)
w1 = L.fit_logit(E[["logvix"]].to_numpy(float), y)
frozen = {"version": "1.1", "score": "n4 = C+B+R+V (unveraendert aus v1.0)", "lesart": "Zustand (Tagesebene)",
          "logit_n4": w.tolist(), "p_je_level": [float(L.predict(w, np.array([[k]]))[0]) for k in range(5)],
          "m1_logvix": w1.tolist(), "E_basisrate": float(y.mean()), "E_gate_tage": int(len(E)),
          "E_von": str(E.index[0].date()), "E_bis": str(E.index[-1].date()), "eingefroren": "2026-11-22"}
(data / "spec_v11_frozen.json").write_text(json.dumps(frozen, indent=1))
print(json.dumps(frozen, indent=1))
