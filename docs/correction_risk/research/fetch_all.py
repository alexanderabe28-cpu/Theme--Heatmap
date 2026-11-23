"""Laedt alle Symbole fuer die v1.1-Forschung. Aufruf: python fetch_all.py <zielordner>
Gibt nur Verfuegbarkeit aus, keine Auswertung."""
import sys, time
from pathlib import Path
import pandas as pd
import yfinance as yf

TICKERS = ["SPY", "RSP", "HYG", "IEF", "XLY", "XLP", "^VIX",            # v1.0
           "IWM", "XLF", "XLB", "XLE", "XLI", "XLK", "XLU", "XLV",       # neue Komponenten
           "^MOVE", "^RUT", "VWEHX", "VFITX", "VADAX"]                   # Proxys / optional
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
cols = {}
for t in TICKERS:
    for attempt in range(3):
        try:
            df = yf.download(t, start="1993-01-01", auto_adjust=True, progress=False, threads=False)
            if df is not None and not df.empty:
                c = df["Close"]
                c = c.iloc[:, 0] if isinstance(c, pd.DataFrame) else c
                cols[t] = c.astype(float)
                break
        except Exception as e:
            print("Fehler", t, e)
        time.sleep(2)
    else:
        print("KEINE DATEN:", t)
px = pd.DataFrame(cols).sort_index()
px.index = pd.to_datetime(px.index).tz_localize(None)
px = px[px["SPY"].notna()]
px.to_csv(out / "prices_all.csv")
info = pd.DataFrame({"start": px.apply(lambda s: s.first_valid_index().date()),
                     "ende": px.apply(lambda s: s.last_valid_index().date()),
                     "n": px.notna().sum(),
                     "luecken_ab_start": px.apply(lambda s: int(s[s.first_valid_index():].isna().sum()))})
print(info.to_string())
