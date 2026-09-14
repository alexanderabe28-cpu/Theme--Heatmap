"""OHLCV-Download von Yahoo Finance fuer tausende Ticker.

Bloecke von ~100 Tickern, Pause dazwischen, Retry fuer fehlgeschlagene
Titel. Yahoo drosselt bei zu vielen Anfragen (Rate-Limit) – dann laenger
warten statt abzubrechen.
"""
import time

import pandas as pd
import yfinance as yf

FIELDS = ["Open", "High", "Low", "Close", "Volume"]


def _download_chunk(tickers: list, start: str) -> dict:
    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False,
                      group_by="column", threads=True, timeout=30)
    out = {}
    if raw is None or raw.empty:
        return out
    for f in FIELDS:
        if f not in raw.columns.get_level_values(0):
            continue
        df = raw[f]
        if isinstance(df, pd.Series):
            df = df.to_frame(name=tickers[0])
        out[f] = df
    return out


def download(tickers: list, start: str, chunk: int = 100,
             pause: float = 1.5) -> dict:
    """Gibt {Feld: DataFrame(Datum x Ticker)} zurueck."""
    tickers = sorted(set(tickers))
    parts = {f: [] for f in FIELDS}
    failed = []

    def run(batch_list, label):
        for i in range(0, len(batch_list), chunk):
            sub = batch_list[i:i + chunk]
            for attempt in range(3):
                try:
                    got = _download_chunk(sub, start)
                    break
                except Exception as e:          # Rate-Limit o.ae.
                    wait = 30 * (attempt + 1)
                    print(f"[prices] {label} Block {i}: {e} – warte {wait}s")
                    time.sleep(wait)
            else:
                got = {}
            close = got.get("Close")
            ok = [] if close is None else \
                [t for t in sub if t in close.columns and close[t].notna().any()]
            failed.extend(t for t in sub if t not in ok)
            for f, df in got.items():
                parts[f].append(df[ok])
            print(f"[prices] {label}: {min(i + chunk, len(batch_list))}/"
                  f"{len(batch_list)} · ok {len(ok)}/{len(sub)}")
            time.sleep(pause)

    run(tickers, "Lauf 1")
    if failed:
        retry, failed[:] = list(failed), []
        print(f"[prices] Retry fuer {len(retry)} Titel in 60s")
        time.sleep(60)
        chunk = 40
        run(retry, "Retry")

    data = {}
    for f, frames in parts.items():
        if frames:
            df = pd.concat(frames, axis=1)
            df = df.loc[:, ~df.columns.duplicated()].sort_index()
            df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
            data[f] = df.astype("float32")
    data["failed"] = sorted(set(failed))
    return data
