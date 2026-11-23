"""Index-Kurse (OHLC) fuer die Charts zum Pine-Indikator. Aufruf: python fetch_index.py <datenordner>"""
import sys
from pathlib import Path
import pandas as pd, yfinance as yf

out = {}
for t in ["^GSPC", "^NDX"]:
    df = yf.download(t, start="2025-06-01", auto_adjust=False, progress=False, threads=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    for c in ["Open", "High", "Low", "Close"]:
        out[f"{t}_{c}"] = df[c].astype(float)
px = pd.DataFrame(out)
px.index = pd.to_datetime(px.index).tz_localize(None)
px.to_csv(Path(sys.argv[1]) / "index_ohlc.csv")
print(px.tail(2).round(2).T)
