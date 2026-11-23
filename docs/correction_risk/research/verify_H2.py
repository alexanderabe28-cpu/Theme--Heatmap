"""Unabhaengige Nachrechnung der Proxy-Aera (Niveau-Spleiss statt Renditekette) und Episodenliste. Nach dem Holdout-Lauf."""
import sys, numpy as np, pandas as pd
px = pd.read_csv(sys.argv[1] + "/prices_all.csv", index_col=0, parse_dates=True)

def splice(etf, proxy):
    t0 = px[etf].first_valid_index()
    f = px.loc[t0, etf] / px.loc[t0, proxy]
    return px[etf].where(px.index >= t0, px[proxy] * f)

def off(x, up=False):
    s, c = x.rolling(50).mean(), x.pct_change(20)
    return ((x > s) & (c > 0)) if up else ((x < s) & (c < 0))

spy = px["SPY"]
gate = spy >= 0.97 * spy.rolling(252).max()
n4 = (off(splice("HYG", "VWEHX") / splice("IEF", "VFITX")).astype(int) + off(splice("RSP", "VADAX")).astype(int)
      + off(px["XLY"] / px["XLP"]).astype(int) + off(px["^VIX"], True).astype(int))
fwd = pd.concat([spy.shift(-i) for i in range(1, 46)], axis=1)
dip = fwd.min(axis=1) / spy - 1
hit = (dip <= -0.05)
pos = pd.Series(np.arange(len(spy)), index=spy.index)
last = pos[:"2007-06-19"].iloc[-1]
m = (spy.index >= "1999-03-18") & (pos + 45 <= last) & gate
print("H2 Gate-Tage", int(m.sum()), "Basisrate %.4f" % hit[m].mean())
for k in range(5):
    mk = m & (n4 == k)
    print(f"  Level {k}: {int(mk.sum())} Tage, {hit[mk].mean():.3f}")
mk = m & (n4 >= 3)
print("  Level>=3:", int(mk.sum()), "Tage, %.3f" % hit[mk].mean())
print("\nTage im Zustand Level>=3 in H2, als Laeufe:")
days = spy.index[mk]
run = [days[0]]
def show(run):
    r = pd.DatetimeIndex(run)
    print(f"  {r[0].date()} bis {r[-1].date()}: {len(r)} Tage, Treffer {int(hit[r].sum())}, schlechtester Dip {dip[r].min():.1%}")
for a, b in zip(days[:-1], days[1:]):
    if pos[b] - pos[a] > 10:
        show(run); run = []
    run.append(b)
show(run)
print("\nGepoolt 1999-2026 (alle drei Stichproben), Zustand je Level:")
last_e = pos[:"2016-12-30"].iloc[-1]
known = fwd.notna().all(axis=1) | hit
seg = (((spy.index >= "1999-03-18") & (pos + 45 <= last)) | ((spy.index >= "2007-06-20") & (pos + 45 <= last_e))
       | (spy.index >= "2017-01-03")) & gate & known
for k in range(5):
    mk = seg & (n4 == k)
    print(f"  Level {k}: {int(mk.sum())} Tage, {hit[mk].mean():.3f}")
print("  Level>=3: %d Tage, %.3f | Basis %d Tage, %.3f" % ((seg & (n4 >= 3)).sum(), hit[seg & (n4 >= 3)].mean(), seg.sum(), hit[seg].mean()))
