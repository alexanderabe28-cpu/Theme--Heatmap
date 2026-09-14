"""Taeglicher Lauf (GitHub Actions nach US-Boersenschluss).

    python -m scanner.run_daily                      # normaler Tageslauf
    python -m scanner.run_daily --backfill-years 2   # Historie aufbauen
    python -m scanner.run_daily --limit 300          # Schnelltest

Schreibt nach data/:
    breadth_daily.csv    Breadth je Tag x Universum (wird fortgeschrieben)
    breadth_weekly.csv   dito je Woche
    benchmarks.csv       SPY / QQQ / IWM Schlusskurse
    scan/snapshot.csv    Scanner-Kennzahlen aller Titel (letzter Tag)
    scan/scan_universe.csv  heutige Scanner-Treffer = eigene Universumsliste
    scan/scan_history.csv   Treffer je Tag (fuer "neu in der Liste")
    meta.json            Laufinfo
"""
import argparse
import json
import os

import pandas as pd

from . import DATA_DIR, SCAN_DIR
from . import metrics, prices, scan, universe

BENCHMARKS = ["SPY", "QQQ", "IWM"]
WARMUP_DAYS = 420          # Kalendertage fuer SMA200 + 20T-Steigung + 52W-Hoch
DAILY_KEEP = 15            # Tageslauf: letzte N Handelstage neu schreiben
UNIVERSES = {
    "sp500": "S&P 500",
    "nasdaq": "Nasdaq Composite",
    "r2000": "Russell 2000",
    "all": "Gesamt",
    "scan": "Scanner-Liste",
}


def merge_csv(path: str, new: pd.DataFrame, keys: list) -> pd.DataFrame:
    """Neue Zeilen ueberschreiben alte mit gleichem Schluessel."""
    if os.path.exists(path):
        old = universe.read_tickers_csv(path)
        old["date"] = pd.to_datetime(old["date"])
        new = pd.concat([old, new]).drop_duplicates(keys, keep="last")
    new = new.sort_values(keys).reset_index(drop=True)
    new.to_csv(path, index=False, date_format="%Y-%m-%d")
    return new


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill-years", type=float, default=0)
    ap.add_argument("--limit", type=int, default=0, help="nur N Titel (Test)")
    ap.add_argument("--refresh-universe", action="store_true")
    args = ap.parse_args()
    os.makedirs(SCAN_DIR, exist_ok=True)

    master = universe.load_or_refresh(force=args.refresh_universe)
    if args.limit:
        master = master.sample(n=min(args.limit, len(master)), random_state=1)
    tickers = master["Ticker"].tolist()

    days = WARMUP_DAYS + int(args.backfill_years * 365)
    start = (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    print(f"[run] {len(tickers)} Titel ab {start}")
    px = prices.download(tickers + BENCHMARKS, start)
    failed = px.pop("failed")
    now_et = pd.Timestamp.now(tz="America/New_York")
    if (px["Close"].index[-1].date() == now_et.date()
            and (now_et.hour, now_et.minute) < (16, 30)):
        print("[run] US-Session laeuft noch – heutiger Balken wird verworfen")
        px = {f: df.iloc[:-1] for f, df in px.items()}
    print(f"[run] geladen: {px['Close'].shape[1]} · fehlgeschlagen: {len(failed)}")

    ind = metrics.compute_indicators(px)
    cfg = scan.load_config()
    mask = scan.scan_mask(ind, master, cfg)

    groups = {
        "sp500": master.loc[master["SP500"], "Ticker"].tolist(),
        "nasdaq": master.loc[master["NASDAQ"], "Ticker"].tolist(),
        "r2000": master.loc[master["R2000"], "Ticker"].tolist(),
        "all": tickers,
    }
    dates = ind["C"].index
    first_valid = dates[min(260, len(dates) - 1)]     # ab hier SMA200/52W belastbar
    keep_from = first_valid if args.backfill_years else \
        max(first_valid, dates[-min(DAILY_KEEP, len(dates))])

    daily_rows, weekly_rows = [], []
    for key in UNIVERSES:
        cols = groups.get(key, tickers)
        m = mask if key == "scan" else None
        d = metrics.breadth(ind, cols, m)
        w = metrics.weekly(d, ind, cols, m)
        d, w = d[d.index >= keep_from], w[w.index >= keep_from]
        if not args.backfill_years and len(w):
            w = w.iloc[-3:]                   # nur volle, frische Wochen neu
        daily_rows.append(d.assign(universe=key).reset_index())
        weekly_rows.append(w.assign(universe=key).reset_index())
        print(f"[run] {UNIVERSES[key]}: {len(cols)} Titel, "
              f"letzter Tag n={int(d['n'].iloc[-1]) if len(d) else 0}")

    order = lambda df: df[["date", "universe"] +
                          [c for c in df.columns if c not in ("date", "universe")]]
    merge_csv(os.path.join(DATA_DIR, "breadth_daily.csv"),
              order(pd.concat(daily_rows)), ["date", "universe"])
    merge_csv(os.path.join(DATA_DIR, "breadth_weekly.csv"),
              order(pd.concat(weekly_rows)), ["date", "universe"])

    bench = px["Close"][[b for b in BENCHMARKS if b in px["Close"]]]
    bench = bench[bench.index >= keep_from].round(4)
    bench.index.name = "date"
    merge_csv(os.path.join(DATA_DIR, "benchmarks.csv"),
              bench.reset_index(), ["date"])

    # --- Scanner-Ausgaben ---
    snap = scan.snapshot(ind, master)
    snap = snap[(snap["Price"] >= 1) & (snap["AVOL"].fillna(0) >= 50_000)]
    num = snap.select_dtypes("number").columns
    snap[num] = snap[num].round(3)
    snap.to_csv(os.path.join(SCAN_DIR, "snapshot.csv"), index=False)

    hits = mask.iloc[-1]
    hit_list = snap[snap["Ticker"].isin(hits[hits].index)]
    hit_list[["Ticker", "Name", "Sector", "Industry"]].to_csv(
        os.path.join(SCAN_DIR, "scan_universe.csv"), index=False)

    hist_days = mask[mask.index >= (keep_from if args.backfill_years
                                    else dates[-1])].iloc[-60:]
    hist = (hist_days.stack().rename("hit").reset_index()
            .rename(columns={"level_0": "date", "Date": "date",
                             "Ticker": "Ticker", "level_1": "Ticker"}))
    hist = hist[hist["hit"]][["date", "Ticker"]]
    merge_csv(os.path.join(SCAN_DIR, "scan_history.csv"), hist,
              ["date", "Ticker"])

    meta = {
        "last_run_utc": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M"),
        "last_date": str(dates[-1].date()),
        "tickers_requested": len(tickers),
        "tickers_loaded": int(px["Close"].columns.isin(tickers).sum()),
        "tickers_failed": len(failed),
        "scan_hits": int(hits.sum()),
        "scan_config": cfg,
        "r2000_source": str(master["R2000_Source"].iloc[0]),
        "universe_updated": str(master["Updated"].iloc[0]),
    }
    with open(os.path.join(DATA_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"[run] fertig · Stand {meta['last_date']} · Scanner-Treffer "
          f"{meta['scan_hits']}")


if __name__ == "__main__":
    main()
