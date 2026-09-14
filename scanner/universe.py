"""Universen: S&P 500, Nasdaq Composite, Russell 2000 – plus Stammdaten
(Name, Sektor, Branche, Market Cap) fuer den Scanner.

Quellen (alle kostenlos):
- Nasdaq-Screener-API: alle US-Aktien je Boerse inkl. Market Cap/Sektor
- Wikipedia: S&P-500-Konstituenten
- iShares IWM-Holdings fuer den Russell 2000. Wird der Abruf geblockt
  (z.B. von EU-IPs), bauen wir den Index nach Russell-Methodik nach:
  US-Aktien nach Market Cap, Rang 1001-3000.
"""
import io
import os
import re
import time

import pandas as pd
import requests

from . import ROOT, UNIVERSE_DIR

UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
}
MASTER_FILE = os.path.join(UNIVERSE_DIR, "master.csv")
SCREENER_URL = ("https://api.nasdaq.com/api/screener/stocks"
                "?tableonly=true&download=true&exchange={ex}")
IWM_URL = ("https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/"
           "1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund")
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# Keine Stammaktien: Warrants, Rights, Units, Vorzuege, Anleihen
NON_COMMON = re.compile(
    r"\b(?:warrants?|rights?|units?|preferred|preference|notes? due|debentures?|"
    r"subordinated|depositary shares?,? each representing)\b", re.I)


def yahoo_symbol(sym: str) -> str:
    """Nasdaq 'BRK/B' bzw. Wikipedia 'BRK.B' -> Yahoo 'BRK-B'."""
    return str(sym).strip().upper().replace("/", "-").replace(".", "-")


def _get(url: str, tries: int = 3, **kw) -> requests.Response:
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=60, **kw)
            r.raise_for_status()
            return r
        except Exception as e:           # Netzfehler/429 -> kurz warten
            last = e
            time.sleep(5 * (i + 1))
    raise last


def fetch_screener(exchange: str) -> pd.DataFrame:
    rows = _get(SCREENER_URL.format(ex=exchange)).json()["data"]["rows"]
    df = pd.DataFrame(rows)
    df = df[~df["symbol"].str.contains(r"\^", regex=True)]
    df = df[~df["name"].fillna("").str.contains(NON_COMMON)]
    df = df[df["industry"].fillna("") != "Blank Checks"]       # SPACs
    out = pd.DataFrame({
        "Ticker": df["symbol"].map(yahoo_symbol),
        "Name": df["name"].str.replace(r"\s+(Common Stock|Class [A-C] "
                                       r"Common Stock|Ordinary Shares)$", "",
                                       regex=True),
        "Exchange": exchange.upper(),
        "Sector": df["sector"].replace("", "Unknown").fillna("Unknown"),
        "Industry": df["industry"].replace("", "Unknown").fillna("Unknown"),
        "Country": df["country"].fillna(""),
        "MarketCap": pd.to_numeric(df["marketCap"], errors="coerce"),
    })
    return out.drop_duplicates("Ticker")


def fetch_sp500() -> set:
    try:
        html = _get(SP500_URL).text
        tbl = pd.read_html(io.StringIO(html))[0]
        syms = {yahoo_symbol(s) for s in tbl["Symbol"]}
        if len(syms) > 450:
            return syms
    except Exception as e:
        print(f"[universe] Wikipedia S&P 500 fehlgeschlagen: {e}")
    # Fallback: vorhandene Liste im Repo
    old = read_tickers_csv(os.path.join(ROOT, "idx_sp500.csv"))
    return {yahoo_symbol(s) for s in old["Ticker"]}


def fetch_r2000_ishares() -> set:
    text = _get(IWM_URL).text
    if text.lstrip().startswith("<"):
        raise RuntimeError("iShares liefert HTML statt CSV (geblockt)")
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("Ticker,"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), on_bad_lines="skip")
    df = df[df["Asset Class"] == "Equity"]
    syms = {yahoo_symbol(s) for s in df["Ticker"].dropna() if str(s) != "-"}
    if len(syms) < 1500:
        raise RuntimeError(f"iShares-Liste unplausibel ({len(syms)} Titel)")
    return syms


def r2000_proxy(all_us: pd.DataFrame) -> set:
    """Russell-Methodik light: US-Firmen nach Market Cap, Rang 1001-3000."""
    us = all_us[(all_us["Country"] == "United States")
                & (all_us["MarketCap"] > 0)]
    ranked = us.sort_values("MarketCap", ascending=False)
    return set(ranked["Ticker"].iloc[1000:3000])


def build_master() -> pd.DataFrame:
    frames = [fetch_screener(ex) for ex in ("nasdaq", "nyse", "amex")]
    all_us = pd.concat(frames).drop_duplicates("Ticker").reset_index(drop=True)
    print(f"[universe] Screener: {len(all_us)} Stammaktien")

    sp500 = fetch_sp500()
    try:
        r2000, r_src = fetch_r2000_ishares(), "iShares IWM"
    except Exception as e:
        print(f"[universe] iShares nicht nutzbar ({e}) -> Russell-Proxy")
        r2000, r_src = r2000_proxy(all_us), "Proxy (Market-Cap-Rang 1001-3000)"

    master = all_us.copy()
    missing = sp500 - set(master["Ticker"])   # z.B. Sonderfaelle in der Notation
    if missing:
        master = pd.concat([master, pd.DataFrame({
            "Ticker": sorted(missing), "Name": sorted(missing),
            "Exchange": "", "Sector": "Unknown", "Industry": "Unknown",
            "Country": "", "MarketCap": float("nan")})])
    master["SP500"] = master["Ticker"].isin(sp500)
    master["NASDAQ"] = master["Exchange"] == "NASDAQ"
    master["R2000"] = master["Ticker"].isin(r2000)
    master = master[master["SP500"] | master["NASDAQ"] | master["R2000"]]
    master["R2000_Source"] = r_src
    master["Updated"] = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    print(f"[universe] S&P 500: {int(master.SP500.sum())} · Nasdaq: "
          f"{int(master.NASDAQ.sum())} · Russell 2000: {int(master.R2000.sum())} "
          f"({r_src}) · gesamt: {len(master)}")
    return master.sort_values("Ticker").reset_index(drop=True)


def read_tickers_csv(path: str) -> pd.DataFrame:
    """CSV mit Ticker-Spalte lesen, ohne dass 'NA'/'NAN' als leer gilt."""
    return pd.read_csv(path, keep_default_na=False, na_values=[""],
                       dtype={"Ticker": str})


def load_or_refresh(max_age_days: int = 7, force: bool = False) -> pd.DataFrame:
    """Stammdaten laden; aelter als max_age_days -> neu bauen. Scheitert der
    Neubau, wird mit der alten Liste weitergearbeitet."""
    os.makedirs(UNIVERSE_DIR, exist_ok=True)
    old = read_tickers_csv(MASTER_FILE) if os.path.exists(MASTER_FILE) else None
    if old is not None and not force:
        age = (pd.Timestamp.now(tz="UTC").tz_localize(None)
               - pd.Timestamp(old["Updated"].iloc[0])).days
        if age < max_age_days:
            return old
    try:
        master = build_master()
        master.to_csv(MASTER_FILE, index=False)
        return master
    except Exception as e:
        if old is None:
            raise
        print(f"[universe] Neubau fehlgeschlagen ({e}) – nutze alte Liste")
        return old
