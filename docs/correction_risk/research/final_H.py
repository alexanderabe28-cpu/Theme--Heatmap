"""Einmaliger Holdout-Lauf fuer Spec v1.1. Aufruf: python final_H.py <datenordner>"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import crlib as L

data = Path(sys.argv[1])
frozen = json.loads((data / "spec_v11_frozen.json").read_text())
W, W1 = np.array(frozen["logit_n4"]), np.array(frozen["m1_logvix"])
d = L.build(pd.read_csv(data / "prices_all.csv", index_col=0, parse_dates=True))
valid = d[d["valid"]]
out = {}


def lead_time(day_pos: int, spy: np.ndarray) -> float:
    w = spy[day_pos + 1: day_pos + 46]
    hit = np.where(w <= 0.95 * spy[day_pos])[0]
    return float(hit[0] + 1) if len(hit) else np.nan


spy_all = d["spy"].to_numpy()
SEGS = tuple(sys.argv[2:]) or ("E", "H1", "H2")
for name in SEGS:
    S = L.segment(d, name)
    A = L.all_days(d, name)
    y = S["y45"].to_numpy()
    base = y.mean()
    lvl = S["level_v10"].to_numpy()
    p = L.predict(W, S[["n4"]].to_numpy(float))
    p1 = L.predict(W1, S[["logvix"]].to_numpy(float))
    r = {"von": str(S.index[0].date()), "bis": str(S.index[-1].date()), "gate_tage": int(len(S)), "basisrate": float(base)}
    print(f"\n===== {name}: {r['von']} bis {r['bis']}, Gate-Tage {len(S)}, Basisrate {base:.1%} =====")
    print(" je Level (Zustand): Tage, geschaetzt, eingetreten")
    r["je_level"] = []
    for k in range(5):
        m = lvl == k
        r["je_level"].append({"level": k, "tage": int(m.sum()), "p": float(frozen["p_je_level"][k]),
                              "quote": float(y[m].mean()) if m.sum() else None})
        print(f"   Level {k}: {m.sum():4d} Tage, {frozen['p_je_level'][k]:.1%}, {y[m].mean() if m.sum() else float('nan'):.1%}")
    r["zustand"], r["erstsignal"] = [], []
    for k in (1, 2, 3, 4):
        st = lvl >= k
        obs, pv, n = L.shift_test(y, st)
        ep = L.cr.episode_starts(valid["level_v10"], k).reindex(A.index).fillna(False)
        e = A[ep.to_numpy() & A["y45"].notna().to_numpy()]
        r["zustand"].append({"k": k, "tage": n, "quote": obs, "p_shift": pv})
        r["erstsignal"].append({"k": k, "episoden": int(len(e)), "treffer": int(e["y45"].sum())})
        print(f"   Level>={k}: Zustand {n} Tage {obs:.1%} p={pv:.3f} | Erstsignal {int(e['y45'].sum())}/{len(e)}")
        if k in (2, 3) and n:
            thr = np.sort(S["vix"].to_numpy())[::-1][n - 1]
            vb = (S["vix"] >= thr).to_numpy()
            o2, p2, n2 = L.shift_test(y, vb)
            r.setdefault("vix_benchmark", []).append({"k": k, "vix_ab": float(thr), "tage": n2, "quote": o2, "p_shift": p2})
            print(f"      VIX-Benchmark gleicher Haeufigkeit (VIX >= {thr:.1f}): {n2} Tage {o2:.1%} p={p2:.3f}")
    print(" Komponenten einzeln:")
    r["komponenten"] = []
    for c in L.COMPS7:
        st = (S[c] == True).to_numpy()  # noqa: E712
        obs, pv, n = L.shift_test(y, st)
        r["komponenten"].append({"c": c, "anteil": n / len(S), "quote": obs, "lift": obs / base, "p_shift": pv})
        print(f"   {c}: {n/len(S):.1%} der Tage, Quote {obs:.1%}, Lift {obs/base:.2f}, p={pv:.3f}")
    t1 = L.block_boot_brier(y, p, None)
    t3 = L.block_boot_brier(y, p, p1)
    t2 = next(z for z in r["zustand"] if z["k"] == 3)
    pv = {"T1": t1["p_one_sided"], "T2": t2["p_shift"], "T3": t3["p_one_sided"]}
    b = L.bh(pv)
    r.update({"auc_modell": L.auc(y, p), "auc_vix": L.auc(y, p1), "brier_modell": L.brier(y, p),
              "brier_konstante": L.brier(y, np.full(len(y), base)), "brier_vix": L.brier(y, p1),
              "T1": t1, "T3": t3, "p": pv, "bh": b})
    print(f" AUC Modell {r['auc_modell']:.3f} | AUC logVIX {r['auc_vix']:.3f}")
    print(f" Brier Modell {r['brier_modell']:.4f} | Konstante {r['brier_konstante']:.4f} | logVIX {r['brier_vix']:.4f}")
    print(f" T1 Brier<Konstante: delta {t1['delta']:+.4f}, p={t1['p_one_sided']:.4f}, BH {b.get('T1')}")
    print(f" T2 Zustand>=3 > Basis: {t2['quote']:.1%} vs {base:.1%}, p={t2['p_shift']:.4f}, BH {b.get('T2')}")
    print(f" T3 Brier<logVIX: delta {t3['delta']:+.4f}, p={t3['p_one_sided']:.4f}, BH {b.get('T3')}")
    st3 = S[lvl >= 3]
    lt = np.array([lead_time(int(q), spy_all) for q in st3.loc[st3["y45"] == 1, "pos"]])
    r["fwd45"] = {"zustand3_mittel": float(st3["fwd45"].mean()), "zustand3_median": float(st3["fwd45"].median()),
                  "gate_mittel": float(S["fwd45"].mean()), "gate_median": float(S["fwd45"].median()),
                  "dip_zustand3_median": float(st3["dip45"].median()), "dip_gate_median": float(S["dip45"].median()),
                  "vorlauf_median": float(np.nanmedian(lt)) if len(lt) else None}
    f = r["fwd45"]
    print(f" 45-Sessions-Rendite: Zustand>=3 Mittel {f['zustand3_mittel']:+.1%} Median {f['zustand3_median']:+.1%} | "
          f"alle Gate-Tage Mittel {f['gate_mittel']:+.1%} Median {f['gate_median']:+.1%}")
    print(f" Median schlechtester Dip: Zustand>=3 {f['dip_zustand3_median']:.1%} | Gate {f['dip_gate_median']:.1%} | "
          f"Vorlauf bis -5 % bei Treffern: Median {f['vorlauf_median']} Sessions")
    out[name] = r

if len(SEGS) < 3:
    sys.exit(0)
print("\n===== Herbst 2026: Tage im Zustand Level >= 3 =====")
h = valid.loc["2026-09-01":]
for ts, row in h[h["level_v10"] >= 3].iterrows():
    comps = "".join(c for c in L.COMPS4 if row[c])
    yy = "offen" if np.isnan(row["y45"]) else int(row["y45"])
    print(f"  {ts.date()} SPY {row['spy']:.2f} Level {int(row['level_v10'])} [{comps}] Y45={yy}")

print("\n===== Gepoolt H1+H2 (nur Holdouts), Zustand je Level =====")
P = pd.concat([L.segment(d, "H2"), L.segment(d, "H1")])
for k in range(5):
    m = P["level_v10"] == k
    print(f"  Level {k}: {int(m.sum())} Tage, eingetreten {P.loc[m, 'y45'].mean():.1%}")
print(f"  Basisrate {P['y45'].mean():.1%}")
(data / "results_v11.json").write_text(json.dumps(out, indent=1, default=float))
