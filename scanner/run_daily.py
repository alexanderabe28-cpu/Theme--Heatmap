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

from . import DATA_DIR, ROOT, SCAN_DIR
from . import metrics, prices, scan, universe

BENCHMARKS = ["SPY", "QQQ", "IWM"]
WARMUP_DAYS = 420          # Kalendertage fuer SMA200 + 20T-Steigung + 52W-Hoch
DAILY_KEEP = 15            # Tageslauf: letzte N Handelstage neu schreiben
UNIVERSES = {
    "sp500": "S&P 500",
    "ndx": "Nasdaq 100",
    "dow": "Dow Jones 30",
    "core": "S&P 500 + Nasdaq 100 + Dow",
    "nasdaq": "Nasdaq Composite",
    "r2000": "Russell 2000",
    "cap1b": "Market Cap ab 1 Mrd $",
    "all": "Gesamt",
    "scan": "Scanner-Liste",
}
INDEX_LISTS = {"ndx": "idx_nasdaq100.csv", "dow": "idx_dow.csv"}


def index_tickers(name: str) -> list:
    """Konstituenten aus den idx_*.csv im Repo (gleiche Listen wie die App)."""
    path = os.path.join(ROOT, INDEX_LISTS[name])
    if not os.path.exists(path):
        return []
    df = universe.read_tickers_csv(path)
    return [universe.yahoo_symbol(t) for t in df["Ticker"]]


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
    # Nasdaq 100 / Dow liegen als Listen im Repo; was dort steht, aber nicht
    # im Master ist (z.B. Nicht-US-ADR), wird mitgeladen
    idx_sets = {k: set(index_tickers(k)) for k in INDEX_LISTS}
    extra = sorted(set().union(*idx_sets.values()) - set(tickers)) if not args.limit else []
    tickers_dl = tickers + extra

    days = WARMUP_DAYS + int(args.backfill_years * 365)
    start = (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    print(f"[run] {len(tickers)} Titel ab {start}")
    px = prices.download(tickers_dl + BENCHMARKS, start)
    failed = px.pop("failed")
    now_et = pd.Timestamp.now(tz="America/New_York")
    if (px["Close"].index[-1].date() == now_et.date()
            and (now_et.hour, now_et.minute) < (16, 30)):
        print("[run] US-Session laeuft noch – heutiger Balken wird verworfen")
        px = {f: df.iloc[:-1] for f, df in px.items()}
    print(f"[run] geladen: {px['Close'].shape[1]} · fehlgeschlagen: {len(failed)}")

    ind = metrics.compute_indicators(px)
    cfg = scan.load_config()

    # Industrie-RS ("One Rule") vor dem Scan: fliesst als Filter und als
    # Spalte in den Snapshot ein
    ind_tbl, ind_per_ticker = scan.industry_rs(ind, master)
    master = master.merge(ind_per_ticker.rename("IndRS"), left_on="Ticker",
                          right_index=True, how="left")
    ind_tbl.reset_index().to_csv(os.path.join(DATA_DIR, "industry_rs.csv"),
                                 index=False)
    print(f"[run] Industrie-RS: {len(ind_tbl)} Industrien mit >= 3 Titeln")

    mask = scan.scan_mask(ind, master, cfg)

    sp500 = master.loc[master["SP500"], "Ticker"].tolist()
    ndx, dow = sorted(idx_sets["ndx"]), sorted(idx_sets["dow"])
    groups = {
        "sp500": sp500,
        "ndx": ndx,
        "dow": dow,
        "core": sorted(set(sp500) | set(ndx) | set(dow)),
        "nasdaq": master.loc[master["NASDAQ"], "Ticker"].tolist(),
        "r2000": master.loc[master["R2000"], "Ticker"].tolist(),
        "cap1b": master.loc[master["MarketCap"] >= 1e9, "Ticker"].tolist(),
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
        "industries_ranked": int(len(ind_tbl)),
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
