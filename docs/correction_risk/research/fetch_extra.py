"""Ergaenzt T-Bill-Zins und QQQ. Aufruf: python fetch_extra.py <datenordner>"""
import sys, time
from pathlib import Path
import pandas as pd
import yfinance as yf
out = Path(sys.argv[1])
cols = {}
for t in ["^IRX", "QQQ"]:
    for _ in range(3):
        df = yf.download(t, start="1993-01-01", auto_adjust=True, progress=False, threads=False)
        if df is not None and not df.empty:
            c = df["Close"]; c = c.iloc[:, 0] if isinstance(c, pd.DataFrame) else c
            cols[t] = c.astype(float); break
        time.sleep(2)
ex = pd.DataFrame(cols).sort_index(); ex.index = pd.to_datetime(ex.index).tz_localize(None)
base = pd.read_csv(out / "prices_all.csv", index_col=0, parse_dates=True)
ex = ex.reindex(base.index)
ex.to_csv(out / "prices_extra.csv")
for c in ex:
    s = ex[c]
    print(c, s.first_valid_index().date(), s.last_valid_index().date(), "Luecken ab 2000:", int(s["2000-01-03":].isna().sum()),
          "| letzter Wert", round(float(s.dropna().iloc[-1]), 2))
print(ex["^IRX"]["2000-01-03":].describe().round(2).to_string())
