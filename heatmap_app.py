# =============================================================
#  Theme-Heatmap  –  Finviz-Stil Treemaps (CBOE-Farblayout)
#  Tab 1: Aktien/ETF-Universum  (Kachel = sqrt(Cap/AUM))
#  Tab 2: Futures/Makro         (Kacheln gleich gross)
#  Farbe = % Change des aktiven Zeitfensters: 1D | 1W | 2W | 4W
#
#  Start:    streamlit run heatmap_app.py
#  Universen: tickers.csv (Aktien/ETF) und futures.csv (Makro)
# =============================================================

import os
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

BASE = os.path.dirname(__file__)
TICKER_FILE = os.path.join(BASE, "tickers.csv")
FUTURES_FILE = os.path.join(BASE, "futures.csv")
WATCHLIST_FILE = os.path.join(BASE, "watchlist.csv")

TIMEFRAMES = {          # Label -> (Handelstage zurueck, Farbskalen-Grenze +/- %)
    "1D": (1, 3.0),
    "1W": (5, 6.0),
    "2W": (10, 9.0),
    "4W": (20, 12.0),
}
# Futures/Makro bewegen sich enger -> eigene, engere Skala (VIX ist der Ausreisser)
TIMEFRAMES_FUT = {
    "1D": (1, 2.0),
    "1W": (5, 4.0),
    "2W": (10, 6.0),
    "4W": (20, 8.0),
}

HISTORY_PERIOD = "6mo"
QUOTE_TTL = 60
PROFILE_TTL = 24 * 3600

# CBOE-Palette: Coral-Rot -> Navy (neutral) -> Mint-Gruen
NAVY_BG = "#16204a"
NAVY_CARD = "#1e2a5a"
MINT = "#3fe0a0"
COLOR_SCALE = [
    (0.00, "#e05a5a"),
    (0.25, "#8f4560"),
    (0.50, NAVY_CARD),
    (0.75, "#2fae85"),
    (1.00, MINT),
]

st.set_page_config(page_title="Theme-Heatmap", layout="wide")

# Aktien/ETF-Map: feste Breite erzwingen (Layout sonst abhaengig von der
# Fensterbreite); bei schmalen Fenstern horizontal scrollen statt stauchen
st.markdown("""<style>
.st-key-map_stocks {overflow-x: auto;}
.st-key-map_stocks div.js-plotly-plot {min-width: 1250px; width: 1250px;}
</style>""", unsafe_allow_html=True)


# ---------------- Universen laden / speichern ----------------
def load_csv(path: str) -> pd.DataFrame:
    # Fehlende Datei darf die App nicht crashen (z.B. waehrend eines
    # Repo-Umbaus) -> leeres Universum zurueckgeben, Tabs zeigen Warnung.
    if not os.path.exists(path):
        st.warning(f"{os.path.basename(path)} fehlt im App-Ordner – "
                   "bitte ins Repo hochladen.")
        return pd.DataFrame(columns=["Ticker", "Theme", "Name"])
    df = pd.read_csv(path)
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()
    if "Theme" not in df.columns:
        df["Theme"] = "Watchlist"
    df["Theme"] = df["Theme"].fillna("Sonstige").astype(str).str.strip()
    if "Name" not in df.columns:
        df["Name"] = df["Ticker"]
    df["Name"] = df["Name"].fillna(df["Ticker"])
    df = df[df["Ticker"] != ""].drop_duplicates(subset="Ticker")
    return df.reset_index(drop=True)


def save_csv(df: pd.DataFrame, path: str) -> None:
    df = df.dropna(subset=["Ticker"])
    df = df[df["Ticker"].astype(str).str.strip() != ""]
    df.to_csv(path, index=False)


# ---------------- Daten holen ----------------
def fetch_closes_ibkr(tickers: tuple, host: str, port: int, client_id: int) -> pd.DataFrame:
    """Daily Closes ueber TWS/IB Gateway (nur US-Aktien/ETFs)."""
    from ib_async import IB, Stock, util
    ib = IB()
    ib.connect(host, port, clientId=client_id, timeout=6)
    frames = {}
    try:
        for t in tickers:
            if "." in t or "-" in t or "=" in t or t.startswith("^"):
                continue
            bars = ib.reqHistoricalData(
                Stock(t, "SMART", "USD"), endDateTime="", durationStr="6 M",
                barSizeSetting="1 day", whatToShow="TRADES", useRTH=True,
            )
            if bars:
                s = util.df(bars).set_index("date")["close"]
                s.index = pd.to_datetime(s.index)
                frames[t] = s
    finally:
        ib.disconnect()
    if not frames:
        raise RuntimeError("IBKR lieferte keine Daten.")
    return pd.DataFrame(frames).dropna(how="all")


@st.cache_data(ttl=QUOTE_TTL, show_spinner=False)
def fetch_closes(tickers: tuple, period: str = HISTORY_PERIOD) -> pd.DataFrame:
    data = yf.download(
        list(tickers), period=period,
        auto_adjust=True, progress=False, group_by="column",
        threads=False,          # Cloud: Thread-je-Ticker sprengt das Limit
    )
    closes = data["Close"]
    if isinstance(closes, pd.Series):
        closes = closes.to_frame(name=tickers[0])
    return closes.dropna(how="all")


@st.cache_data(ttl=PROFILE_TTL, show_spinner=False)
def fetch_sizes(tickers: tuple) -> pd.Series:
    sizes = {}
    for t in tickers:
        size = np.nan
        try:
            tk = yf.Ticker(t)
            size = tk.fast_info.get("marketCap")
            if not size:
                size = tk.info.get("totalAssets") or tk.info.get("marketCap")
        except Exception:
            pass
        sizes[t] = float(size) if size else np.nan
    return pd.Series(sizes, name="Size")


RS_UNIVERSE_FILE = os.path.join(BASE, "rs_universe.csv")
RS_TTL = 12 * 3600      # RS/Breadth 12 h zwischenspeichern


def bulk_download(tickers: list, period: str, chunk: int = 60) -> dict:
    """Grosse Universen in Bloecken laden, ohne yfinance-Threading.

    yfinance startet mit threads=True einen Thread je Ticker – bei 500+
    Titeln laeuft die Streamlit-Cloud-Instanz ins Thread-Limit
    (RuntimeError: can't start new thread). Sequenzielle Bloecke von 60
    Tickern sind etwas langsamer, aber stabil.
    """
    parts = {}
    for i in range(0, len(tickers), chunk):
        sub = tickers[i:i + chunk]
        try:
            raw = yf.download(sub, period=period, auto_adjust=True,
                              progress=False, group_by="column",
                              threads=False)
        except Exception:
            continue
        for field in ["Open", "High", "Low", "Close", "Volume"]:
            if field not in raw:
                continue
            df = raw[field]
            if isinstance(df, pd.Series):
                df = df.to_frame(name=sub[0])
            parts.setdefault(field, []).append(df)
    return {f: pd.concat(v, axis=1) for f, v in parts.items()}


@st.cache_data(ttl=RS_TTL, show_spinner=False)
def fetch_universe_ohlcv(extra_symbols: tuple) -> dict:
    """OHLCV fuer das S&P-500-Universum (+ Watchlist). Ein Download fuer
    RS-Rating UND Breadth-Panel."""
    try:
        uni = pd.read_csv(RS_UNIVERSE_FILE)["Ticker"].astype(str).tolist()
    except Exception:
        uni = []
    symbols = sorted(set(uni) | {s.upper() for s in extra_symbols})
    return bulk_download(symbols, "18mo")


@st.cache_data(ttl=RS_TTL, show_spinner=False)
def compute_ibd_rs(extra_symbols: tuple) -> pd.Series:
    """IBD-Stil RS-Rating (1-99).

    Gewichtete 12-Monats-Performance: 40 % juengstes Quartal, je 20 % die drei
    davor. Anschliessend Perzentilrang im Vergleichsuniversum (S&P 500 +
    eigene Watchlist-Namen).

    Hinweis: Proxy, nicht das offizielle IBD-Rating – IBD rankt gegen ~7000
    Titel, hier sind es ~500. Reihenfolge und Groessenordnung stimmen gut
    ueberein, einzelne Werte koennen um einige Punkte abweichen.
    """
    data = fetch_universe_ohlcv(extra_symbols).get("Close")
    if data is None:
        return pd.Series(dtype="Int64")

    scores = {}
    for col in data.columns:
        s = data[col].dropna()
        if len(s) < 253:
            continue                       # weniger als 12 Monate Historie
        q1 = s.iloc[-1] / s.iloc[-64] - 1        # juengstes Quartal
        q2 = s.iloc[-64] / s.iloc[-127] - 1
        q3 = s.iloc[-127] / s.iloc[-190] - 1
        q4 = s.iloc[-190] / s.iloc[-253] - 1
        scores[col] = 0.4 * q1 + 0.2 * q2 + 0.2 * q3 + 0.2 * q4
    sc = pd.Series(scores).dropna()
    if sc.empty:
        return pd.Series(dtype="Int64")
    return (sc.rank(pct=True) * 98 + 1).round().astype(int)


@st.cache_data(ttl=QUOTE_TTL, show_spinner=False)
def compute_breadth(extra_symbols: tuple) -> dict:
    """Breadth-Kennzahlen (Snapshot letzter Handelstag) gegen das
    S&P-500-Universum. Definitionen:
    - NH/NL: Close ueber/unter dem 252-Tage-Extrem (exkl. heute)
    - A/D: Close vs. Vortags-Close
    - Up/Down from Open: Close vs. heutiges Open
    - Up/Down on Volume: A/D-Richtung UND Volumen > 50-Tage-Schnitt
    - Up 4% / Down 4%: Tagesaenderung >= +4 % bzw. <= -4 %
    - Stages (Weinstein-Naeherung via SMA200 und dessen 20-Tage-Steigung)
    """
    d = fetch_universe_ohlcv(extra_symbols)
    C, O, V = d.get("Close"), d.get("Open"), d.get("Volume")
    H, L = d.get("High"), d.get("Low")
    if C is None or len(C) < 260:
        return {}
    prev = C.iloc[-2]
    last = C.iloc[-1]
    chg = last / prev - 1

    hi252 = (H if H is not None else C).iloc[-253:-1].max()
    lo252 = (L if L is not None else C).iloc[-253:-1].min()
    res = {
        "nh": int((last > hi252).sum()), "nl": int((last < lo252).sum()),
        "adv": int((chg > 0).sum()), "dec": int((chg < 0).sum()),
    }
    if O is not None:
        fo = last / O.iloc[-1] - 1
        res["up_open"] = int((fo > 0).sum()); res["dn_open"] = int((fo < 0).sum())
    if V is not None:
        v50 = V.iloc[-51:-1].mean()
        hivol = V.iloc[-1] > v50
        res["up_vol"] = int(((chg > 0) & hivol).sum())
        res["dn_vol"] = int(((chg < 0) & hivol).sum())
    res["up4"] = int((chg >= 0.04).sum()); res["dn4"] = int((chg <= -0.04).sum())

    # Above/Below SMA50 und SMA200
    sma50 = C.rolling(50).mean().iloc[-1]
    res["ab50"] = int((last > sma50).sum())
    res["bl50"] = int((last < sma50).sum())
    sma200_last = C.rolling(200).mean().iloc[-1]
    res["ab200"] = int((last > sma200_last).sum())
    res["bl200"] = int((last < sma200_last).sum())

    # Stage-Analyse
    sma200 = C.rolling(200).mean()
    slope = sma200.iloc[-1] / sma200.iloc[-21] - 1
    above = last > sma200.iloc[-1]
    rising = slope > 0.002          # +0.2 % ueber 20 Tage = steigend
    falling = slope < -0.002
    valid = sma200.iloc[-1].notna()
    st1 = (~above & ~falling & valid)              # Bodenbildung
    st2 = (above & rising & valid)                 # Aufwaertstrend
    st3 = (above & ~rising & valid)                # Topbildung
    st4 = (~above & falling & valid)               # Abwaertstrend
    res["stages"] = [int(st1.sum()), int(st2.sum()),
                     int(st3.sum()), int(st4.sum())]
    res["date"] = str(C.index[-1].date())
    res["n"] = int(valid.sum())
    return res


def compute_changes(closes: pd.DataFrame) -> pd.DataFrame:
    """% Change je Zeitfenster – pro Ticker auf eigenen validen Datenpunkten.
    (Zeilenbasiert + ffill wuerde bei asynchronen Sessions, z.B. FX vs. Equity,
    faelschlich 0.00 % liefern, wenn die juengste Zeile fuer einen Ticker leer ist.)"""
    out = {label: {} for label in TIMEFRAMES}
    last_all = {}
    for col in closes.columns:
        s = closes[col].dropna()
        if s.empty:
            for label in TIMEFRAMES:
                out[label][col] = np.nan
            last_all[col] = np.nan
            continue
        last = s.iloc[-1]
        last_all[col] = last
        for label, (n_days, _) in TIMEFRAMES.items():
            out[label][col] = (last / s.iloc[-(n_days + 1)] - 1.0) * 100.0 \
                if len(s) > n_days else np.nan
    df = pd.DataFrame(out)
    df["Last"] = pd.Series(last_all)
    return df


@st.cache_data(ttl=QUOTE_TTL, show_spinner=False)
def fetch_ohlc(ticker: str, period: str = "1y") -> pd.DataFrame:
    """OHLCV fuer den Detail-Chart eines einzelnen Symbols."""
    df = yf.download(ticker, period=period, auto_adjust=True,
                     progress=False, group_by="column", threads=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(how="all")


def render_detail_chart(ticker: str, label: str) -> None:
    """Candlestick + EMA21/50 + Volumen unter der Heatmap."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    with st.spinner(f"Lade Chart {ticker}..."):
        d = fetch_ohlc(ticker)
    if d.empty or "Close" not in d:
        st.warning(f"Keine Chartdaten fuer {ticker}.")
        return

    ema21 = d["Close"].ewm(span=21, adjust=False).mean()
    ema50 = d["Close"].ewm(span=50, adjust=False).mean()
    has_vol = "Volume" in d and d["Volume"].fillna(0).sum() > 0

    fig = make_subplots(rows=2 if has_vol else 1, cols=1, shared_xaxes=True,
                        row_heights=[0.75, 0.25] if has_vol else [1.0],
                        vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(
        x=d.index, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"],
        name=ticker, increasing=dict(line=dict(color=MINT), fillcolor=MINT),
        decreasing=dict(line=dict(color="#e05a5a"), fillcolor="#e05a5a"),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=ema21, name="EMA 21",
                             line=dict(color="#ffd166", width=1.3)), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=ema50, name="EMA 50",
                             line=dict(color="#7aa2ff", width=1.3)), row=1, col=1)
    if has_vol:
        colors = [MINT if c >= o else "#e05a5a"
                  for o, c in zip(d["Open"], d["Close"])]
        fig.add_trace(go.Bar(x=d.index, y=d["Volume"], name="Volumen",
                             marker_color=colors, opacity=0.6), row=2, col=1)

    fig.update_layout(
        title=dict(text=f"{label} · {ticker} · 1 Jahr",
                   font=dict(size=15, color="#fff")),
        height=460, margin=dict(t=45, l=0, r=0, b=0),
        paper_bgcolor=NAVY_BG, plot_bgcolor=NAVY_BG, font=dict(color="#fff"),
        xaxis_rangeslider_visible=False, bargap=0.1,
        legend=dict(orientation="h", y=1.10, x=1, xanchor="right"),
    )
    fig.update_xaxes(gridcolor="#243063", rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_yaxes(gridcolor="#243063")
    st.plotly_chart(fig, use_container_width=True, key=f"detail_{ticker}")

    last = float(d["Close"].iloc[-1])
    st.caption(
        f"Letzter Kurs {last:,.2f} · EMA21 {ema21.iloc[-1]:,.2f} "
        f"({'darueber' if last >= ema21.iloc[-1] else 'darunter'}) · "
        f"EMA50 {ema50.iloc[-1]:,.2f} "
        f"({'darueber' if last >= ema50.iloc[-1] else 'darunter'})"
    )


@st.cache_data(ttl=QUOTE_TTL, show_spinner=False)
def fetch_signals(tickers: tuple) -> pd.DataFrame:
    """RVOL (Run-Rate) und ATR%-Extension je Ticker.

    RVOL: heutiges Volumen / 50-Tage-Schnitt. Laeuft die US-Session noch,
    wird das Tagesvolumen auf die bereits verstrichene Handelszeit hoch-
    gerechnet (Run-Rate-Logik) statt naiv gegen den Tagesschnitt zu stellen.
    ATR-Ext: (Close - EMA21) / ATR14 – Werte um +-4 markieren Ueberdehnung.
    """
    d = bulk_download(list(tickers), "4mo")
    if not d:
        return pd.DataFrame()
    C, H, L, V = d["Close"], d["High"], d["Low"], d["Volume"]
    if isinstance(C, pd.Series):
        C = C.to_frame(tickers[0]); H = H.to_frame(tickers[0])
        L = L.to_frame(tickers[0]); V = V.to_frame(tickers[0])

    # Session-Fortschritt (US-Boerse 9:30-16:00 ET) fuer Run-Rate
    now_et = pd.Timestamp.now(tz="America/New_York")
    frac = 1.0
    live_bar = False            # letzter Bar = heutige (laufende/fertige) Session?
    if C.index[-1].date() == now_et.date():
        mins = (now_et.hour * 60 + now_et.minute) - (9 * 60 + 30)
        if mins > 0:
            live_bar = True
            frac = min(max(mins / 390.0, 0.08), 1.0)

    out = {}
    for t in C.columns:
        c = C[t].dropna()
        if len(c) < 60:
            continue
        v = V[t].reindex(c.index)
        if live_bar:
            v50 = v.iloc[-51:-1].mean()
            rvol_live = (v.iloc[-1] / frac) / v50 if v50 and v50 > 0 else np.nan
            v50p = v.iloc[-52:-2].mean()
            rvol_prev = v.iloc[-2] / v50p if v50p and v50p > 0 else np.nan
        else:
            # Pre-Market/nach Feierabend: letzter Bar = kompletter Vortag
            rvol_live = np.nan
            v50 = v.iloc[-51:-1].mean()
            rvol_prev = v.iloc[-1] / v50 if v50 and v50 > 0 else np.nan
        h, l = H[t].reindex(c.index), L[t].reindex(c.index)
        tr = pd.concat([h - l, (h - c.shift()).abs(),
                        (l - c.shift()).abs()], axis=1).max(axis=1)
        atr14 = tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1]
        ema21 = c.ewm(span=21, adjust=False).mean().iloc[-1]
        ext = (c.iloc[-1] - ema21) / atr14 if atr14 and atr14 > 0 else np.nan
        out[t] = {"RVOL_live": rvol_live, "RVOL_prev": rvol_prev,
                  "ATRext": ext}
    return pd.DataFrame(out).T


def col_pct(v):
    """Zell-Faerbung fuer %-Werte (Tabellen)."""
    if pd.isna(v):
        return ""
    if v > 0.05:
        return f"background-color: rgba(63,224,160,{min(abs(v)/8,0.85):.2f}); color: #fff"
    if v < -0.05:
        return f"background-color: rgba(224,90,90,{min(abs(v)/8,0.85):.2f}); color: #fff"
    return f"background-color: {NAVY_CARD}; color: #fff"


# ---------------- Treemap-Renderer ----------------
def render_treemap(df: pd.DataFrame, tf: str, limit: float, key: str,
                   label_col: str = "Ticker",
                   signals: pd.DataFrame | None = None,
                   keep_order: bool = False) -> str | None:
    """Zeichnet die Treemap und gibt den angeklickten Ticker zurueck (oder None).
    signals: optionale RVOL/ATRext-Tabelle -> Tooltip-Zeilen + Mint-Rahmen
    bei RVOL >= 1.5.
    keep_order: True = Gruppen in Datenreihenfolge platzieren (oben links
    zuerst) statt nach Flaechengroesse zu sortieren."""
    df = df.copy()
    if signals is not None:
        df = df.merge(signals, left_on="Ticker", right_index=True, how="left")
    else:
        df["RVOL_live"] = np.nan
        df["RVOL_prev"] = np.nan
        df["ATRext"] = np.nan
    # Rahmen-Trigger: live wenn Session laeuft, sonst Vortag
    df["RVOL_hot"] = df["RVOL_live"].fillna(df["RVOL_prev"])
    df["RVOLtxt"] = df.apply(
        lambda r: (f"live {r.RVOL_live:.2f} · VT {r.RVOL_prev:.2f}"
                   if pd.notna(r.RVOL_live)
                   else (f"VT {r.RVOL_prev:.2f}" if pd.notna(r.RVOL_prev)
                         else "–")), axis=1)
    df["EXTtxt"] = df["ATRext"].apply(
        lambda v: f"{v:+.1f}" if pd.notna(v) else "–")
    # Langname fuer Kachel-Zeile 3 (gekuerzt, damit kleine Kacheln lesbar bleiben)
    if "Name" in df.columns:
        df["ShortName"] = df["Name"].astype(str).apply(
            lambda s: s if len(s) <= 30 else s[:29] + "…")
    else:
        df["ShortName"] = ""
        df["Name"] = df["Ticker"]
    fig = px.treemap(
        df,
        path=[px.Constant("Alle"), "Theme", label_col],
        values="Size",
        color=tf,
        color_continuous_scale=COLOR_SCALE,
        range_color=(-limit, limit),
        custom_data=["Last", "1D", "1W", "2W", "4W", "Ticker", "ShortName",
                     "Name", "RVOLtxt", "EXTtxt"],
    )
    idx = list(TIMEFRAMES.keys()).index(tf) + 1
    fig.update_traces(
        texttemplate=("<b>%{label}</b><br>%{customdata[" + str(idx) + "]:.2f} %"
                      "<br><span style='font-size:10px'>%{customdata[6]}</span>"),
        textposition="middle center",
        hovertemplate=(
            "<b>%{customdata[5]}</b> · %{customdata[7]}<br>"
            "Kurs: %{customdata[0]:,.2f}<br>"
            "1D: %{customdata[1]:.2f} %<br>"
            "1W: %{customdata[2]:.2f} %<br>"
            "2W: %{customdata[3]:.2f} %<br>"
            "4W: %{customdata[4]:.2f} %<br>"
            "RVOL: %{customdata[8]} · ATR-Ext: %{customdata[9]}"
            "<extra></extra>"
        ),
        marker=dict(line=dict(width=1.5, color=NAVY_BG)),
    )
    if keep_order:
        fig.update_traces(sort=False)
    # Mint-Rahmen fuer Kacheln mit RVOL >= 1.5 (Blattebene). Plotly haengt
    # Gruppen-Knoten hinter die Blaetter -> Arrays entsprechend auffuellen.
    if signals is not None and df["RVOL_hot"].notna().any():
        leaf = fig.data[0]
        lookup = df.set_index(label_col)
        colors, widths = [], []
        for lab in (leaf.labels if leaf.labels is not None else []):
            rv = lookup["RVOL_hot"].get(lab, np.nan) \
                if lab in lookup.index else np.nan
            hot = pd.notna(rv) and rv >= 1.5
            colors.append(MINT if hot else NAVY_BG)
            widths.append(3.0 if hot else 1.5)
        if colors:
            fig.update_traces(marker=dict(
                line=dict(width=widths, color=colors)))
    fig.update_layout(
        margin=dict(t=10, l=0, r=0, b=0),
        height=760, width=1250,        # feste Masse: Layout auf jedem
        autosize=False,                # Bildschirm identisch (Packing haengt
                                       # sonst von der Fensterbreite ab)
        paper_bgcolor=NAVY_BG,
        font=dict(family="Arial Black, Arial, sans-serif", color="#ffffff"),
        coloraxis_colorbar=dict(title="%", tickfont=dict(color="#ffffff")),
    )
    st.caption("Tipp: Kachel anklicken -> Detail-Chart erscheint darunter.")
    event = st.plotly_chart(fig, width="content", key=key, theme=None,
                            on_select="rerun", selection_mode="points")

    # Angeklickte Kachel -> Ticker aufloesen (nur Blattebene, keine Gruppen)
    try:
        pts = event["selection"]["points"]
    except (TypeError, KeyError):
        pts = []
    if not pts:
        return None
    label = pts[0].get("label")
    hit = df[df[label_col] == label]
    return None if hit.empty else str(hit["Ticker"].iloc[0])


def prepare(universe: pd.DataFrame, closes: pd.DataFrame,
            sizes: pd.Series | None, tf: str) -> pd.DataFrame:
    changes = compute_changes(closes)
    df = universe.merge(changes, left_on="Ticker", right_index=True, how="left")
    if sizes is not None:
        df = df.merge(sizes, left_on="Ticker", right_index=True, how="left")
        df["Size"] = df["Size"].fillna(df["Size"].median()).clip(lower=1)
        df["Size"] = np.sqrt(df["Size"])       # Rangfolge bleibt, Kleine lesbar
        # Deckel bei 2.5x Median: Mega-AUM (SPY/QQQ/GLD) erdrueckt sonst
        # die Theme-Gruppen -> Broad Market bleibt auf Gruppen-Niveau
        df["Size"] = df["Size"].clip(upper=df["Size"].median() * 2.5)
    else:
        df["Size"] = 1.0                        # Futures: gleich grosse Kacheln
    missing = df[df[tf].isna()]["Ticker"].tolist()
    if missing:
        st.caption(f"Ohne Daten (ignoriert): {', '.join(missing)}")
    return df.dropna(subset=[tf])


# ---------------- UI ----------------
st.title("Theme-Heatmap")

with st.sidebar:
    st.subheader("Datenquelle (Aktien/ETF)")
    source = st.radio("Quelle", ["Yahoo Finance (~15 min)", "IBKR (TWS/Gateway, live)"],
                      label_visibility="collapsed")
    use_ibkr = source.startswith("IBKR")
    if use_ibkr:
        ib_host = st.text_input("Host", "127.0.0.1")
        ib_port = st.number_input("Port (7496 live / 7497 paper)", value=7496, step=1)
        ib_cid = st.number_input("Client-ID", value=17, step=1)
    st.caption("Futures/Makro laufen immer ueber Yahoo.")
    st.subheader("Auto-Refresh")
    interval = st.selectbox("Intervall", ["Aus", "30 s", "60 s", "5 min"], index=2,
                            label_visibility="collapsed")
    if st.button("Jetzt aktualisieren"):
        st.cache_data.clear()

ms = {"Aus": 0, "30 s": 30_000, "60 s": 60_000, "5 min": 300_000}[interval]
if ms:
    st_autorefresh(interval=ms, key="auto_refresh")

(tab_map, tab_idx, tab_fut, tab_watch, tab_ovsd, tab_gen, tab_breadth,
 tab_scan, tab_themes, tab_cal, tab_gate, tab_universe) = st.tabs(
    ["Aktien / ETF", "Index-Maps", "Futures / Makro", "Watchlist", "OvsD",
     "Generaele", "Breadth", "Scanner", "Theme Tracker", "Kalender",
     "Gate-Check", "Universum"])

# ----- Tab 1: Aktien/ETF -----
with tab_map:
    universe = load_csv(TICKER_FILE)
    if universe.empty:
        st.warning("Universum leer – Tab 'Universum'.")
    else:
        tf = st.radio("Zeitfenster", list(TIMEFRAMES.keys()), horizontal=True,
                      label_visibility="collapsed", key="tf_stocks")
        tickers = tuple(universe["Ticker"])
        with st.spinner("Lade Kurse..."):
            closes = None
            if use_ibkr:
                try:
                    closes = fetch_closes_ibkr(tickers, ib_host, int(ib_port), int(ib_cid))
                    skipped = [t for t in tickers if t not in closes.columns]
                    st.sidebar.success(f"IBKR: {closes.shape[1]} Ticker")
                    if skipped:
                        st.sidebar.caption(f"Yahoo-Fallback: {', '.join(skipped)}")
                        closes = closes.join(fetch_closes(tuple(skipped)), how="outer")
                except Exception as e:
                    st.sidebar.error(f"IBKR nicht erreichbar ({e}) – Fallback Yahoo.")
            if closes is None:
                closes = fetch_closes(tickers)
            sizes = fetch_sizes(tickers)
        with st.spinner("Berechne RVOL / ATR-Extension..."):
            sig = fetch_signals(tickers)
        df = prepare(universe, closes, sizes, tf)
        if df.empty:
            st.error("Keine Kursdaten – Ticker pruefen.")
        else:
            limit = TIMEFRAMES[tf][1]
            picked = render_treemap(df, tf, limit, key="map_stocks",
                                    signals=sig, keep_order=True)
            if not sig.empty:
                sig_hot = sig.copy()
                sig_hot["hot"] = sig_hot["RVOL_live"].fillna(
                    sig_hot["RVOL_prev"])
                live_mode = sig_hot["RVOL_live"].notna().any()
                hot = sig_hot[sig_hot["hot"] >= 1.5].sort_values(
                    "hot", ascending=False)
                mode_txt = ("live, Run-Rate" if live_mode
                            else "Abschluss Vortag – Boerse geschlossen")
                if not hot.empty:
                    st.caption(
                        f"Mint-Rahmen = RVOL >= 1.5 ({mode_txt}): "
                        + " · ".join(f"{t} {r.hot:.1f}x"
                                     for t, r in hot.head(8).iterrows()))
                else:
                    st.caption(f"RVOL-Modus: {mode_txt} · kein Wert >= 1.5.")
            st.caption(
                f"{tf} = letzter Kurs vs. Close vor {TIMEFRAMES[tf][0]} Handelstag(en) · "
                f"Skala ±{limit:.0f} % · Stand: {closes.index[-1]:%Y-%m-%d} · "
                f"Quelle: {'IBKR' if use_ibkr else 'Yahoo (~15 min)'}"
            )
            if picked:
                nm = df[df["Ticker"] == picked]["Name"]
                render_detail_chart(picked, nm.iloc[0] if len(nm) else picked)

            # --- Tabelle: alle Werte unter der Map ---
            st.markdown("#### Alle Werte")
            tbl_all = df[["Ticker", "Name", "Theme", "Last",
                          "1D", "1W", "2W", "4W"]].copy()
            tbl_all = tbl_all.rename(columns={"Last": "Kurs"})
            tbl_all = tbl_all.merge(sig, left_on="Ticker", right_index=True,
                                    how="left")
            tbl_all = tbl_all.rename(columns={
                "ATRext": "ATR-Ext", "RVOL_live": "RVOL live",
                "RVOL_prev": "RVOL VT"})
            tbl_all = (tbl_all.sort_values("1D", ascending=False)
                       .reset_index(drop=True))
            pct_c = ["1D", "1W", "2W", "4W"]

            def col_rvol(v):
                if pd.isna(v):
                    return ""
                if v >= 1.5:
                    return "background-color: rgba(63,224,160,0.75); color: #fff"
                if v >= 1.0:
                    return f"background-color: {NAVY_CARD}; color: #fff"
                return "color: #9fb0e8"

            st.dataframe(
                tbl_all.style
                .map(col_pct, subset=pct_c)
                .map(col_rvol, subset=["RVOL live", "RVOL VT"])
                .format({"Kurs": "{:,.2f}", "RVOL live": "{:.2f}",
                         "RVOL VT": "{:.2f}",
                         "ATR-Ext": "{:+.1f}",
                         **{c: "{:+.2f} %" for c in pct_c}}),
                use_container_width=True, hide_index=True,
                height=42 + 35 * len(tbl_all),
            )
            st.caption("Sortiert nach 1D · Spaltenkopf anklicken zum "
                       "Umsortieren · RVOL >= 1.5 hervorgehoben.")

# ----- Tab 2: Futures/Makro -----
with tab_fut:
    fut = load_csv(FUTURES_FILE)
    if fut.empty:
        st.warning("futures.csv ist leer.")
    else:
        tff = st.radio("Zeitfenster", list(TIMEFRAMES_FUT.keys()), horizontal=True,
                       label_visibility="collapsed", key="tf_fut")
        with st.spinner("Lade Futures..."):
            closes_f = fetch_closes(tuple(fut["Ticker"]))
        dff = prepare(fut, closes_f, None, tff)
        if dff.empty:
            st.error("Keine Futures-Daten.")
        else:
            limit_f = TIMEFRAMES_FUT[tff][1]
            picked_f = render_treemap(dff, tff, limit_f, key="map_fut",
                                      label_col="Name")
            st.caption(
                f"{tff} = letzter Kurs vs. Close vor {TIMEFRAMES_FUT[tff][0]} Handelstag(en) · "
                f"Skala ±{limit_f:.0f} % · Kacheln gleich gross · Stand: "
                f"{closes_f.index[-1]:%Y-%m-%d} · Quelle: Yahoo. "
                f"Hinweis: VIX/VIX3M sind hier roh dargestellt – gruen = Vola steigt."
            )
            if picked_f:
                nm = dff[dff["Ticker"] == picked_f]["Name"]
                render_detail_chart(picked_f,
                                    nm.iloc[0] if len(nm) else picked_f)

# ----- Tab 3: Watchlist -----
with tab_watch:
    wl = load_csv(WATCHLIST_FILE) if os.path.exists(WATCHLIST_FILE) else pd.DataFrame(
        columns=["Ticker", "Theme", "Name"])
    col_l, col_r = st.columns([3, 1])
    with col_r:
        st.caption("Ticker pflegen (Yahoo-Notation):")
        wl_edit = st.data_editor(
            wl[["Ticker"]], num_rows="dynamic", use_container_width=True, key="ed_watch")
        if st.button("Watchlist speichern", type="primary"):
            save_csv(wl_edit, WATCHLIST_FILE)
            st.cache_data.clear()
            st.rerun()
    with col_l:
        if wl.empty:
            st.info("Watchlist leer – rechts Ticker eintragen und speichern.")
        else:
            with st.spinner("Lade Watchlist..."):
                closes_w = fetch_closes(tuple(wl["Ticker"]))
            chg_w = compute_changes(closes_w)
            tbl = wl[["Ticker"]].merge(chg_w, left_on="Ticker", right_index=True,
                                       how="left")
            tbl = tbl[["Ticker", "Last", "1D", "1W", "2W", "4W"]]
            tbl = tbl.rename(columns={"Last": "Kurs"})
            tbl = tbl.sort_values("1D", ascending=False).reset_index(drop=True)

            # --- IBD-RS-Rating (optional, da Universum-Download ~2 min) ---
            if st.session_state.get("rs_on"):
                with st.spinner("Berechne IBD-RS gegen S&P-500-Universum..."):
                    rs = compute_ibd_rs(tuple(tbl["Ticker"]))
                tbl.insert(2, "RS", tbl["Ticker"].map(rs).astype("Int64"))
                tbl = tbl.sort_values("RS", ascending=False).reset_index(drop=True)
            else:
                st.button("IBD-RS berechnen (~2 Min, dann 12 h gecacht)",
                          key="rs_btn",
                          on_click=lambda: st.session_state.update(rs_on=True))

            pct_cols = ["1D", "1W", "2W", "4W"]

            def col_rs(v):
                """RS-Faerbung nach O'Neil-Schwellen: >=90 stark, <70 schwach."""
                if pd.isna(v):
                    return ""
                if v >= 90:
                    return "background-color: rgba(63,224,160,0.85); color: #fff"
                if v >= 80:
                    return "background-color: rgba(63,224,160,0.45); color: #fff"
                if v >= 70:
                    return f"background-color: {NAVY_CARD}; color: #fff"
                return "background-color: rgba(224,90,90,0.55); color: #fff"

            fmt = {"Kurs": "{:,.2f}"}
            fmt.update({c: "{:+.2f} %" for c in pct_cols})
            styled = (tbl.style
                      .map(col_pct, subset=pct_cols)
                      .format(fmt))
            if "RS" in tbl.columns:
                styled = styled.map(col_rs, subset=["RS"])
            st.caption("Tipp: Kaestchen links neben dem Ticker anklicken "
                       "-> Detail-Chart erscheint darunter.")
            ev = st.dataframe(styled, use_container_width=True, hide_index=True,
                              height=42 + 35 * len(tbl), key="wl_table",
                              on_select="rerun", selection_mode="single-row")
            missing_w = tbl[tbl["1D"].isna()]["Ticker"].tolist()
            if missing_w:
                st.caption(f"Ohne Daten: {', '.join(missing_w)}")
            st.caption(
                f"Sortiert nach {'RS' if 'RS' in tbl.columns else '1D'} · "
                f"Stand: {closes_w.index[-1]:%Y-%m-%d} · Quelle: Yahoo (~15 min)"
                + (" · RS = IBD-Stil (40/20/20/20-Quartalsgewichtung), "
                   "Perzentil gegen S&P 500 – Proxy, nicht das offizielle "
                   "IBD-Rating (das rankt gegen ~7000 Titel)."
                   if "RS" in tbl.columns else "")
            )
            try:
                rows = ev["selection"]["rows"]
            except (TypeError, KeyError):
                rows = []
            if rows:
                sym = str(tbl.iloc[rows[0]]["Ticker"])
                render_detail_chart(sym, sym)

# ----- Tab 4: OvsD (Offensiv vs. Defensiv) -----
OVSD_UNIVERSE = pd.DataFrame({
    "Ticker": ["XLK", "XLC", "XLY", "XLU", "XLV", "XLP"],
    "Theme": ["Offensiv", "Offensiv", "Offensiv",
              "Defensiv", "Defensiv", "Defensiv"],
    "Name": ["XLK · Tech", "XLC · Comm", "XLY · Discretionary",
             "XLU · Utilities", "XLV · Health", "XLP · Staples"],
})

with tab_ovsd:
    tfo = st.radio("Zeitfenster", list(TIMEFRAMES.keys()), horizontal=True,
                   label_visibility="collapsed", key="tf_ovsd")
    with st.spinner("Lade Sektoren..."):
        closes_o = fetch_closes(tuple(OVSD_UNIVERSE["Ticker"]), period="1y")
    dfo = prepare(OVSD_UNIVERSE, closes_o, None, tfo)
    if not dfo.empty:
        # Gleiche Gesamtflaeche pro Gruppe (sonst dominiert Zyklisch mit 5 Kacheln)
        dfo["Size"] = dfo.groupby("Theme")["Ticker"].transform(lambda s: 3.0 / len(s))
    if dfo.empty:
        st.error("Keine Sektordaten.")
    else:
        limit_o = TIMEFRAMES_FUT[tfo][1]      # Sektoren: engere Makro-Skala
        with st.spinner("Berechne RVOL / ATR-Extension..."):
            sig_o = fetch_signals(tuple(OVSD_UNIVERSE["Ticker"]))
        picked_o = render_treemap(dfo, tfo, limit_o, key="map_ovsd",
                                  label_col="Name", signals=sig_o)
        if not sig_o.empty:
            so = sig_o.copy()
            so["hot"] = so["RVOL_live"].fillna(so["RVOL_prev"])
            live_mode_o = so["RVOL_live"].notna().any()
            hot_o = so[so["hot"] >= 1.5].sort_values("hot", ascending=False)
            mode_o = ("live, Run-Rate" if live_mode_o
                      else "Abschluss Vortag – Boerse geschlossen")
            if not hot_o.empty:
                st.caption(f"Mint-Rahmen = RVOL >= 1.5 ({mode_o}): "
                           + " · ".join(f"{t} {r.hot:.1f}x"
                                        for t, r in hot_o.iterrows()))
            else:
                st.caption(f"RVOL-Modus: {mode_o} · kein Wert >= 1.5.")
        if picked_o:
            nm = dfo[dfo["Ticker"] == picked_o]["Name"]
            render_detail_chart(picked_o, nm.iloc[0] if len(nm) else picked_o)

        # --- Tabelle: alle Werte ---
        tbl_o = dfo[["Ticker", "Name", "Theme", "Last",
                     "1D", "1W", "2W", "4W"]].copy()
        tbl_o = tbl_o.rename(columns={"Last": "Kurs"})
        tbl_o = tbl_o.merge(sig_o, left_on="Ticker", right_index=True,
                            how="left")
        tbl_o = tbl_o.rename(columns={"ATRext": "ATR-Ext",
                                      "RVOL_live": "RVOL live",
                                      "RVOL_prev": "RVOL VT"})
        tbl_o = tbl_o.sort_values("1D", ascending=False).reset_index(drop=True)
        pct_o = ["1D", "1W", "2W", "4W"]

        def col_rvol_o(v):
            if pd.isna(v):
                return ""
            if v >= 1.5:
                return "background-color: rgba(63,224,160,0.75); color: #fff"
            if v >= 1.0:
                return f"background-color: {NAVY_CARD}; color: #fff"
            return "color: #9fb0e8"

        st.dataframe(
            tbl_o.style
            .map(col_pct, subset=pct_o)
            .map(col_rvol_o, subset=["RVOL live", "RVOL VT"])
            .format({"Kurs": "{:,.2f}", "RVOL live": "{:.2f}",
                     "RVOL VT": "{:.2f}", "ATR-Ext": "{:+.1f}",
                     **{c: "{:+.2f} %" for c in pct_o}}),
            use_container_width=True, hide_index=True,
            height=42 + 35 * len(tbl_o),
        )

        # --- OvsD-Indikator: Offense-Komposit / Defense-Komposit ---
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        col_mode, col_info = st.columns([1, 3])
        with col_mode:
            ovsd_mode = st.radio("Modus", ["Rolling", "Cumulative"],
                                 horizontal=True, key="ovsd_mode")

        c = closes_o.ffill().dropna()
        # Indikator bleibt bewusst auf den 3v3-Kernkompositen (dein Framework);
        # die Zyklisch/Neutral-Gruppe geht nur in die Heatmap, nicht ins Ratio.
        if ovsd_mode == "Rolling":
            off = (c["XLK"] + c["XLC"] + c["XLY"]) / 3.0
            def_ = (c["XLU"] + c["XLV"] + c["XLP"]) / 3.0
        else:   # Cumulative: Komposits auf 100 rebasiert ab Fensterstart
            reb = c / c.iloc[0] * 100.0
            off = (reb["XLK"] + reb["XLC"] + reb["XLY"]) / 3.0
            def_ = (reb["XLU"] + reb["XLV"] + reb["XLP"]) / 3.0
        ratio = (off / def_) * 100.0
        ema21 = ratio.ewm(span=21, adjust=False).mean()
        roc5 = ratio.pct_change(5) * 100.0            # Rotations-RoC (5 Tage)
        regime63 = ratio - ratio.shift(63)            # 63-Tage-Regime

        figo = make_subplots(rows=2, cols=1, shared_xaxes=True,
                             row_heights=[0.72, 0.28], vertical_spacing=0.04)
        figo.add_trace(go.Scatter(x=ratio.index, y=ema21, name="EMA 21",
                                  line=dict(color="#e05a5a", width=1.5)),
                       row=1, col=1)
        figo.add_trace(go.Scatter(x=ratio.index, y=ratio, name="OvsD-Ratio",
                                  line=dict(color=MINT, width=2.2),
                                  fill="tonexty",
                                  fillcolor="rgba(63,224,160,0.12)"),
                       row=1, col=1)
        figo.add_trace(go.Bar(x=roc5.index, y=roc5, name="RoC 5T",
                              marker_color=[MINT if v >= 0 else "#e05a5a"
                                            for v in roc5.fillna(0)]),
                       row=2, col=1)
        figo.add_hline(y=0, line=dict(color="#243063", width=1), row=2, col=1)

        # 63-Tage-Regime als Hintergrund (gruen = Offense-Regime, rot = Defense)
        reg = (regime63 > 0)
        seg_start = None
        prev = None
        for ts, val in reg.dropna().items():
            if prev is None or val != prev:
                if seg_start is not None:
                    figo.add_vrect(x0=seg_start, x1=ts,
                                   fillcolor=MINT if prev else "#e05a5a",
                                   opacity=0.07, line_width=0)
                seg_start = ts
            prev = val
        if seg_start is not None and prev is not None:
            figo.add_vrect(x0=seg_start, x1=reg.index[-1],
                           fillcolor=MINT if prev else "#e05a5a",
                           opacity=0.07, line_width=0)

        figo.update_layout(
            title=dict(text=f"OvsD-Indikator ({ovsd_mode}) · "
                            "(XLK+XLC+XLY) / (XLU+XLV+XLP) · ×100",
                       font=dict(size=15, color="#fff")),
            height=480, margin=dict(t=45, l=0, r=0, b=0),
            paper_bgcolor=NAVY_BG, plot_bgcolor=NAVY_BG,
            font=dict(color="#fff"), showlegend=True,
            legend=dict(orientation="h", y=1.10, x=1, xanchor="right"),
            bargap=0.1,
        )
        figo.update_xaxes(gridcolor="#243063")
        figo.update_yaxes(gridcolor="#243063", title_text="Ratio", row=1, col=1)
        figo.update_yaxes(gridcolor="#243063", title_text="RoC %", row=2, col=1)
        st.plotly_chart(figo, use_container_width=True, key="ovsd_line")

        above = ratio.iloc[-1] >= ema21.iloc[-1]
        r63 = regime63.dropna()
        reg_txt = ""
        if not r63.empty:
            reg_txt = (" · 63T-Regime: "
                       + ("OFFENSE (gruener Hintergrund)" if r63.iloc[-1] > 0
                          else "DEFENSE (roter Hintergrund)"))
        st.caption(
            f"Ratio {'ueber' if above else 'unter'} EMA-21 -> "
            f"{'Offense fuehrt (Risk-ON-Neigung)' if above else 'Defense fuehrt (Risk-OFF-Neigung)'} · "
            f"Letzter Wert: {ratio.iloc[-1]:.2f} vs. EMA {ema21.iloc[-1]:.2f}"
            f"{reg_txt} · Stand: {c.index[-1]:%Y-%m-%d}"
        )

# ----- Tab: Generaele (Mega-Cap-Baskets vs. Fussvolk) -----
GENERALS_FILE = os.path.join(BASE, "generals.csv")

with tab_gen:
    if not os.path.exists(GENERALS_FILE):
        st.error("generals.csv fehlt im App-Ordner.")
    else:
        gcol1, gcol2 = st.columns([3, 2])
        with gcol1:
            tfg = st.radio("Zeitfenster", list(TIMEFRAMES.keys()),
                           horizontal=True, label_visibility="collapsed",
                           key="tf_gen")
        with gcol2:
            agg_mode = st.radio("Aggregation", ["Median", "Mean"],
                                horizontal=True, key="gen_agg",
                                label_visibility="collapsed")

        gens = pd.read_csv(GENERALS_FILE)
        gens["Ticker"] = gens["Ticker"].astype(str).str.upper().str.strip()
        ew_map = gens.groupby("Sektor")["EW_ETF"].first().to_dict()
        allsyms = tuple(sorted(set(gens["Ticker"])
                               | set(gens["EW_ETF"].dropna()) | {"SPY"}))
        with st.spinner("Lade Generaele..."):
            closes_g = fetch_closes(allsyms)
        chg_g = compute_changes(closes_g)[tfg]

        spy = chg_g.get("SPY", np.nan)
        rows = []
        for sek, grp in gens.groupby("Sektor"):
            vals = chg_g.reindex(grp["Ticker"]).dropna()
            if vals.empty:
                continue
            agg = vals.median() if agg_mode == "Median" else vals.mean()
            ew = chg_g.get(ew_map.get(sek), np.nan)
            rows.append({
                "Sektor": sek,
                "Generaele %": agg,
                "vs SPY %": agg - spy,
                "Fussvolk (EW-ETF) %": ew,
                "Spread G-EW %": agg - ew if pd.notna(ew) else np.nan,
                "Staerkster": f"{vals.idxmax()} {vals.max():+.1f}%",
                "Schwaechster": f"{vals.idxmin()} {vals.min():+.1f}%",
            })
        gdf = (pd.DataFrame(rows)
               .sort_values("vs SPY %", ascending=False)
               .reset_index(drop=True))

        num_cols = ["Generaele %", "vs SPY %", "Fussvolk (EW-ETF) %",
                    "Spread G-EW %"]
        st.dataframe(
            gdf.style
            .map(col_pct, subset=num_cols)
            .format({c: "{:+.2f} %" for c in num_cols}),
            use_container_width=True, hide_index=True,
            height=42 + 35 * len(gdf),
        )
        st.caption(
            f"SPY {tfg}: {spy:+.2f} % · Baskets equal-weight "
            f"({agg_mode}) · Fussvolk = Invesco Equal-Weight-Sektor-ETF · "
            f"Spread > 0: Generaele fuehren, Spread < 0: Breite fuehrt · "
            f"Stand: {closes_g.index[-1]:%Y-%m-%d}"
        )

        # Mitglieder-Detail: Sektor waehlen
        sel_g = st.selectbox("Basket-Detail", ["–"] + gdf["Sektor"].tolist(),
                             label_visibility="collapsed")
        if sel_g != "–":
            grp = gens[gens["Sektor"] == sel_g]
            mem = pd.DataFrame({
                "Ticker": grp["Ticker"],
                f"{tfg} %": chg_g.reindex(grp["Ticker"]).values,
            }).dropna()
            mem["vs SPY %"] = mem[f"{tfg} %"] - spy
            mem = mem.sort_values(f"{tfg} %", ascending=False)
            st.dataframe(
                mem.style
                .map(col_pct, subset=[f"{tfg} %", "vs SPY %"])
                .format({f"{tfg} %": "{:+.2f} %", "vs SPY %": "{:+.2f} %"}),
                use_container_width=True, hide_index=True,
            )
        st.caption("Baskets editierbar im Tab 'Universum' (generals.csv): "
                   "Ticker, Sektor, EW_ETF.")

# ----- Tab 5: Breadth -----
def breadth_card(left_lbl: str, right_lbl: str, up: int, down: int,
                 mid_lbl: str = "") -> str:
    """Kompakte Karte im Stil der TradingView-Leiste: gruen links, rot rechts,
    geteilter Balken. Gibt HTML zurueck."""
    total = max(up + down, 1)
    lp, rp = up / total * 100, down / total * 100
    mid = (f"<span style='color:#9fb0e8;font-size:12px'>{mid_lbl}</span>"
           if mid_lbl else "")
    html = f"""
    <div style="background:#10182f;border:1px solid #243063;border-radius:8px;
                padding:10px 12px;flex:1;min-width:230px">
      <div style="display:flex;justify-content:space-between;align-items:baseline">
        <span style="color:{MINT};font-weight:800;font-size:13px">{left_lbl}</span>
        {mid}
        <span style="color:#e05a5a;font-weight:800;font-size:13px">{right_lbl}</span>
      </div>
      <div style="display:flex;justify-content:space-between;margin:3px 0 6px">
        <span style="color:{MINT};font-size:13px;font-weight:700">
          {lp:.1f} % ({up})</span>
        <span style="color:#e05a5a;font-size:13px;font-weight:700">
          ({down}) {rp:.1f} %</span>
      </div>
      <div style="display:flex;height:7px;border-radius:4px;overflow:hidden;
                  background:#243063">
        <div style="background:{MINT};width:{lp:.1f}%"></div>
        <div style="width:2px"></div>
        <div style="background:#e05a5a;width:{rp:.1f}%"></div>
      </div>
    </div>"""
    # Einzeilig ausgeben: eingerueckte Zeilen wuerden Markdown-Codebloecke ausloesen
    return " ".join(line.strip() for line in html.splitlines())


# ----- Daten aus dem taeglichen GitHub-Actions-Lauf (scanner/run_daily.py) -----
DATA_DIR = os.path.join(BASE, "data")
SCAN_DIR = os.path.join(DATA_DIR, "scan")
SCANNER_CONFIG = os.path.join(BASE, "scanner_config.json")
BREADTH_UNIVERSES = {
    "sp500": "S&P 500", "nasdaq": "Nasdaq Composite", "r2000": "Russell 2000",
    "all": "Gesamt (alle drei)", "scan": "Scanner-Liste",
}
BENCH_FOR = {"sp500": "SPY", "nasdaq": "QQQ", "r2000": "IWM",
             "all": "SPY", "scan": "SPY"}
BREADTH_RANGES = {"3M": 63, "6M": 126, "1J": 252, "2J": 504, "Alles": None}
BREADTH_PANELS = ["Benchmark", "% ueber Moving Averages", "Stages",
                  "Neue Hochs - Tiefs", "A/D-Linie", "McClellan-Oszillator",
                  "Up 4% / Down 4%", "Stockbee-Ratio 5T / 10T",
                  "+-25 % im Quartal", "Scanner-Treffer"]
TREND_OPTS = {None: "aus", "stage2": "Stage 2 (ueber steigender SMA200)",
              "sma50_above_sma200": "SMA50 > SMA200",
              "above_sma200": "Close > SMA200"}


def read_data_csv(path: str) -> pd.DataFrame:
    """Daten-CSV lesen; Ticker wie 'NA' bleiben Ticker statt NaN."""
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, keep_default_na=False, na_values=[""])
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_breadth(freq: str) -> pd.DataFrame:
    return read_data_csv(os.path.join(DATA_DIR, f"breadth_{freq}.csv"))


@st.cache_data(ttl=600, show_spinner=False)
def load_benchmarks() -> pd.DataFrame:
    return read_data_csv(os.path.join(DATA_DIR, "benchmarks.csv"))


@st.cache_data(ttl=600, show_spinner=False)
def load_data_meta() -> dict:
    import json as _json
    path = os.path.join(DATA_DIR, "meta.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return _json.load(f)


def breadth_derived(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """A/D-Linie, NH-NL, McClellan und Stockbee-Ratios aus der Rohreihe."""
    d = df.sort_values("date").set_index("date").copy()
    d["ad_net"] = d["adv"] - d["dec"]
    d["ad_line"] = d["ad_net"].cumsum()
    d["nh_nl"] = d["nh"] - d["nl"]
    tot = (d["adv"] + d["dec"]).where(lambda s: s > 0)
    rana = (d["adv"] - d["dec"]) / tot * 1000       # ratio-adjusted
    d["mcclellan"] = (rana.ewm(span=19, adjust=False).mean()
                      - rana.ewm(span=39, adjust=False).mean())
    if freq == "daily":
        for n in (5, 10):
            dn = d["dn4"].rolling(n).sum()
            d[f"ratio{n}"] = d["up4"].rolling(n).sum() / dn.where(dn > 0)
    else:
        d["ratio5"] = d["up4"] / d["dn4"].where(d["dn4"] > 0)
        d["ratio10"] = np.nan
    return d


def render_breadth_chart(d: pd.DataFrame, panels: list, bench: pd.Series | None,
                         bench_sym: str, scan_n: pd.Series | None,
                         freq: str) -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    red, blue, yellow, pink = "#e05a5a", "#7aa2ff", "#ffd166", "#ff5fa2"
    titles = {
        "Benchmark": f"{bench_sym} (Schlusskurs)",
        "% ueber Moving Averages": "% ueber SMA20 (gelb) · SMA50 (mint) · "
                                   "SMA200 (blau) · T2108/SMA40 (pink)",
        "Stages": "Stage 2 Aufwaertstrend (blau) vs. Stage 4 Abwaertstrend "
                  "(pink) in %",
        "Neue Hochs - Tiefs": "Neue 52W-Hochs minus -Tiefs",
        "A/D-Linie": "Advance/Decline-Linie (kumuliert)",
        "McClellan-Oszillator": "McClellan-Oszillator (ratio-adjusted)",
        "Up 4% / Down 4%": "Up 4 % (mint) / Down 4 % (rot) mit Volumen",
        "Stockbee-Ratio 5T / 10T": ("Up4/Down4-Ratio 5 Tage (mint) · "
                                    "10 Tage (gelb)" if freq == "daily"
                                    else "Up4/Down4-Ratio je Woche"),
        "+-25 % im Quartal": "+25 % (mint) / -25 % (rot) in 65 Tagen",
        "Scanner-Treffer": "Titel, die den Scanner bestanden haetten",
    }
    fig = make_subplots(rows=len(panels), cols=1, shared_xaxes=True,
                        vertical_spacing=0.045,
                        subplot_titles=[titles[p] for p in panels])
    x = d.index
    sign_colors = lambda s: [MINT if v >= 0 else red for v in s.fillna(0)]

    for row, p in enumerate(panels, start=1):
        add = lambda tr: fig.add_trace(tr, row=row, col=1)
        if p == "Benchmark" and bench is not None:
            add(go.Scatter(x=x, y=bench.reindex(x), name=bench_sym,
                           line=dict(color="#ffffff", width=1.6)))
        elif p == "% ueber Moving Averages":
            for col, nm, c in [("p_ab20", "SMA20", yellow), ("p_ab50", "SMA50", MINT),
                               ("p_ab200", "SMA200", blue), ("p_ab40", "T2108", pink)]:
                add(go.Scatter(x=x, y=d[col], name=nm,
                               line=dict(color=c, width=1.5)))
            for lvl in (20, 80):
                fig.add_hline(y=lvl, line=dict(color="#4a5a8a", dash="dot",
                                               width=1), row=row, col=1)
        elif p == "Stages":
            add(go.Scatter(x=x, y=d["p_s2"], name="Stage 2",
                           line=dict(color=blue, width=1.8)))
            add(go.Scatter(x=x, y=d["p_s4"], name="Stage 4",
                           line=dict(color=pink, width=1.8)))
        elif p == "Neue Hochs - Tiefs":
            add(go.Bar(x=x, y=d["nh_nl"], name="NH-NL",
                       marker_color=sign_colors(d["nh_nl"])))
        elif p == "A/D-Linie":
            add(go.Scatter(x=x, y=d["ad_line"], name="A/D",
                           line=dict(color=MINT, width=1.6)))
        elif p == "McClellan-Oszillator":
            add(go.Bar(x=x, y=d["mcclellan"], name="McClellan",
                       marker_color=sign_colors(d["mcclellan"])))
        elif p == "Up 4% / Down 4%":
            add(go.Bar(x=x, y=d["up4"], name="Up 4%", marker_color=MINT))
            add(go.Bar(x=x, y=-d["dn4"], name="Down 4%", marker_color=red))
        elif p == "Stockbee-Ratio 5T / 10T":
            add(go.Scatter(x=x, y=d["ratio5"], name="Ratio 5T",
                           line=dict(color=MINT, width=1.5)))
            if d["ratio10"].notna().any():
                add(go.Scatter(x=x, y=d["ratio10"], name="Ratio 10T",
                               line=dict(color=yellow, width=1.5)))
            fig.add_hline(y=1, line=dict(color="#4a5a8a", dash="dot", width=1),
                          row=row, col=1)
        elif p == "+-25 % im Quartal":
            add(go.Bar(x=x, y=d["up25q"], name="+25 %", marker_color=MINT))
            add(go.Bar(x=x, y=-d["dn25q"], name="-25 %", marker_color=red))
        elif p == "Scanner-Treffer" and scan_n is not None:
            add(go.Bar(x=x, y=scan_n.reindex(x), name="Treffer",
                       marker_color=blue))

    fig.update_layout(
        height=210 * len(panels) + 40, margin=dict(t=30, l=0, r=0, b=0),
        paper_bgcolor=NAVY_BG, plot_bgcolor=NAVY_BG, font=dict(color="#fff"),
        showlegend=False, barmode="relative", bargap=0.15, hovermode="x unified",
    )
    fig.update_annotations(font=dict(size=12, color="#cfd6f0"), x=0,
                           xanchor="left")
    fig.update_xaxes(gridcolor="#243063",
                     rangebreaks=[dict(bounds=["sat", "mon"])]
                     if freq == "daily" else None)
    fig.update_yaxes(gridcolor="#243063", zerolinecolor="#4a5a8a")
    st.plotly_chart(fig, use_container_width=True, key="breadth_hist")


with tab_breadth:
    meta_b = load_data_meta()
    raw_b = pd.DataFrame()
    if meta_b:
        bc1, bc2, bc3 = st.columns([2, 1.2, 2.2])
        with bc1:
            br_uni = st.selectbox("Universum", list(BREADTH_UNIVERSES),
                                  format_func=BREADTH_UNIVERSES.get,
                                  key="br_uni", label_visibility="collapsed")
        with bc2:
            br_freq_lbl = st.radio("Ansicht", ["Tag", "Woche"], horizontal=True,
                                   key="br_freq", label_visibility="collapsed")
        with bc3:
            br_rng = st.radio("Zeitraum", list(BREADTH_RANGES), index=2,
                              horizontal=True, key="br_rng",
                              label_visibility="collapsed")
        br_freq = "daily" if br_freq_lbl == "Tag" else "weekly"
        raw_b = load_breadth(br_freq)

    if raw_b.empty:
        st.info("Noch keine Breadth-Historie im Repo. Auf GitHub unter "
                "**Actions -> Daily Breadth -> Run workflow** einmal mit "
                "`backfill_years = 2` starten; danach laeuft die Erfassung "
                "jeden Handelstag automatisch.")
    else:
        d_all = breadth_derived(raw_b[raw_b["universe"] == br_uni], br_freq)
        n_rows = BREADTH_RANGES[br_rng]
        if n_rows and br_freq == "weekly":
            n_rows = max(n_rows // 5, 4)
        d_b = d_all.iloc[-n_rows:] if n_rows else d_all

        # --- Karten: letzter Tag / letzte Woche ---
        last_b = d_all.iloc[-1]
        n_b = int(last_b["n"])

        def split(p):
            up = int(round((p if pd.notna(p) else 0) / 100 * n_b))
            return up, max(n_b - up, 0)

        row1 = (
            breadth_card("Advancing", "Declining", int(last_b["adv"]),
                         int(last_b["dec"]))
            + breadth_card("New High", "New Low", int(last_b["nh"]),
                           int(last_b["nl"]))
            + breadth_card("Above", "Below", *split(last_b["p_ab50"]), "SMA50")
            + breadth_card("Above", "Below", *split(last_b["p_ab200"]), "SMA200")
        )
        row2 = (
            breadth_card("Up on Volume", "Down on Volume",
                         int(last_b["up_vol"]), int(last_b["dn_vol"]))
            + breadth_card("Up 4%", "Down 4%", int(last_b["up4"]),
                           int(last_b["dn4"]))
            + breadth_card("+25% Quartal", "-25% Quartal",
                           int(last_b["up25q"]), int(last_b["dn25q"]))
            + breadth_card("EMA10>20>SMA50", "nicht", *split(last_b["p_stack"]))
        )
        st.markdown(f"<div style='display:flex;gap:10px;flex-wrap:wrap'>{row1}"
                    f"</div><div style='display:flex;gap:10px;flex-wrap:wrap;"
                    f"margin-top:10px'>{row2}</div>", unsafe_allow_html=True)
        per = "Woche bis" if br_freq == "weekly" else "Stand"
        st.caption(
            f"{BREADTH_UNIVERSES[br_uni]} · {n_b} Titel · {per} "
            f"{d_all.index[-1]:%d.%m.%Y} · Stage 2: {last_b['p_s2']:.0f} % · "
            f"Stage 4: {last_b['p_s4']:.0f} % · T2108: {last_b['p_ab40']:.0f} % · "
            f"McClellan: {last_b['mcclellan']:+.0f}"
            + (" · Woche: Hochs/Tiefs, Up4/Down4 und Volumen = Wochensumme"
               if br_freq == "weekly" else ""))

        # --- Verlauf ---
        default_panels = ["Benchmark", "% ueber Moving Averages",
                          "Neue Hochs - Tiefs", "Up 4% / Down 4%",
                          "McClellan-Oszillator"]
        if br_uni == "scan":
            default_panels = ["Benchmark", "Scanner-Treffer",
                              "% ueber Moving Averages", "Up 4% / Down 4%"]
        panels = st.multiselect("Charts", BREADTH_PANELS, default=default_panels,
                                key=f"br_panels_{br_uni}")
        bench_df = load_benchmarks()
        bsym = BENCH_FOR[br_uni]
        bench_s = (bench_df.set_index("date")[bsym]
                   if not bench_df.empty and bsym in bench_df else None)
        scan_rows = raw_b[raw_b["universe"] == "scan"].set_index("date")["n"]
        if panels:
            render_breadth_chart(d_b, [p for p in BREADTH_PANELS if p in panels],
                                 bench_s, bsym, scan_rows, br_freq)

        # --- Market Monitor (Stockbee-Stil) ---
        st.markdown("#### Market Monitor")
        mon = d_all.iloc[::-1].head(30 if br_freq == "daily" else 26)
        mon_tbl = pd.DataFrame({
            "Datum": mon.index.strftime("%d.%m.%y"),
            "Up 4%": mon["up4"], "Down 4%": mon["dn4"],
            "Ratio 5T": mon["ratio5"], "Ratio 10T": mon["ratio10"],
            "+25% Q": mon["up25q"], "-25% Q": mon["dn25q"],
            "+13% 34T": mon["up13_34"], "-13% 34T": mon["dn13_34"],
            "NH": mon["nh"], "NL": mon["nl"],
            "% >SMA20": mon["p_ab20"], "T2108": mon["p_ab40"],
            "% >SMA50": mon["p_ab50"], "% >SMA200": mon["p_ab200"],
            "% Stage 2": mon["p_s2"],
            bsym: (bench_s.reindex(mon.index).values
                   if bench_s is not None else np.nan),
        })

        def col_ratio(v):
            if pd.isna(v):
                return ""
            if v >= 2:
                return "background-color: rgba(63,224,160,0.7); color: #fff"
            if v <= 0.5:
                return "background-color: rgba(224,90,90,0.7); color: #fff"
            return ""

        def col_level(v):
            if pd.isna(v):
                return ""
            if v >= 60:
                return f"background-color: rgba(63,224,160,{min((v-50)/60, .8):.2f}); color: #fff"
            if v <= 40:
                return f"background-color: rgba(224,90,90,{min((50-v)/60, .8):.2f}); color: #fff"
            return ""

        def hl_pairs(row):
            styles = [""] * len(row)
            for a, b in (("Up 4%", "Down 4%"), ("+25% Q", "-25% Q"),
                         ("+13% 34T", "-13% 34T"), ("NH", "NL")):
                ia, ib = row.index.get_loc(a), row.index.get_loc(b)
                if row[a] > row[b] * 1.5:
                    styles[ia] = "color: #3fe0a0; font-weight: 700"
                elif row[b] > row[a] * 1.5:
                    styles[ib] = "color: #e05a5a; font-weight: 700"
            return styles

        pct_mon = ["% >SMA20", "T2108", "% >SMA50", "% >SMA200", "% Stage 2"]
        st.dataframe(
            mon_tbl.style
            .apply(hl_pairs, axis=1)
            .map(col_ratio, subset=["Ratio 5T", "Ratio 10T"])
            .map(col_level, subset=pct_mon)
            .format({"Ratio 5T": "{:.2f}", "Ratio 10T": "{:.2f}", bsym: "{:,.2f}",
                     **{c: "{:.1f}" for c in pct_mon}}, na_rep="–"),
            use_container_width=True, hide_index=True,
            height=42 + 35 * len(mon_tbl),
        )
        st.caption(
            f"Letzter Datenlauf: {meta_b.get('last_run_utc', '?')} UTC · "
            f"{meta_b.get('tickers_loaded', '?')}/{meta_b.get('tickers_requested', '?')} "
            f"Titel geladen · Russell 2000: {meta_b.get('r2000_source', '?')} · "
            "Historie mit heutiger Index-Zusammensetzung (Survivorship-Bias) · "
            "Up/Down 4 % = Stockbee (Volumen > Vortag, >= 100k) · "
            "NH/NL = 252-Tage-Extreme.")

# ----- Tab: Scanner (eigene Universumsliste) -----
@st.cache_data(ttl=600, show_spinner=False)
def load_scan_snapshot() -> pd.DataFrame:
    return read_data_csv(os.path.join(SCAN_DIR, "snapshot.csv"))


@st.cache_data(ttl=600, show_spinner=False)
def load_scan_history() -> pd.DataFrame:
    return read_data_csv(os.path.join(SCAN_DIR, "scan_history.csv"))


def load_scanner_config() -> dict:
    import json as _json
    if not os.path.exists(SCANNER_CONFIG):
        return {}
    with open(SCANNER_CONFIG, encoding="utf-8") as f:
        return {k: v for k, v in _json.load(f).items() if not k.startswith("_")}


with tab_scan:
    snap = load_scan_snapshot()
    if snap.empty:
        st.info("Noch kein Scanner-Snapshot – er entsteht beim taeglichen "
                "GitHub-Actions-Lauf (data/scan/snapshot.csv).")
    else:
        cfg_s = load_scanner_config()

        def fnum(col, label, key, default, step=1.0, scale=1.0):
            val = None if default is None else float(default) / scale
            return col.number_input(label, value=val, step=step, key=key,
                                    placeholder="aus")

        with st.expander("Filter", expanded=True):
            f1 = st.columns(4)
            f_uni = f1[0].multiselect("Index", ["S&P 500", "Nasdaq", "Russell 2000"],
                                      placeholder="alle", key="sc_uni")
            f_sec = f1[1].multiselect("Sektor", sorted(snap["Sector"].dropna().unique()),
                                      placeholder="alle", key="sc_sec")
            trend_keys = list(TREND_OPTS)
            f_trend = f1[2].selectbox(
                "Trend", trend_keys, format_func=TREND_OPTS.get, key="sc_trend",
                index=trend_keys.index(cfg_s.get("trend"))
                if cfg_s.get("trend") in trend_keys else 0)
            f_rs = fnum(f1[3], "RS min (1-99)", "sc_rs", cfg_s.get("min_rs"))

            f2 = st.columns(4)
            f_price = fnum(f2[0], "Kurs min $", "sc_price", cfg_s.get("min_price"))
            f_cap = fnum(f2[1], "Market Cap min (Mio $)", "sc_cap",
                         cfg_s.get("min_market_cap"), step=100.0, scale=1e6)
            f_avol = fnum(f2[2], "AVOL min (Tsd. Stueck)", "sc_avol",
                          cfg_s.get("min_avol"), step=100.0, scale=1e3)
            f_rvol = fnum(f2[3], "RVOL min", "sc_rvol", cfg_s.get("min_rvol"), step=0.1)

            f3 = st.columns(6)
            f_atr_lo = fnum(f3[0], "ATR% min", "sc_atr_lo", cfg_s.get("min_atr_pct"), 0.5)
            f_atr_hi = fnum(f3[1], "ATR% max", "sc_atr_hi", cfg_s.get("max_atr_pct"), 0.5)
            f_g50_lo = fnum(f3[2], "Gain vom MA50 % min", "sc_g_lo", cfg_s.get("min_gain50"))
            f_g50_hi = fnum(f3[3], "Gain vom MA50 % max", "sc_g_hi", cfg_s.get("max_gain50"))
            f_ax_lo = fnum(f3[4], "ATR%-Multiple MA50 min", "sc_ax_lo",
                           cfg_s.get("min_atrx50"), 0.5)
            f_ax_hi = fnum(f3[5], "ATR%-Multiple MA50 max", "sc_ax_hi",
                           cfg_s.get("max_atrx50"), 0.5)

            f4 = st.columns(3)
            f_c10 = f4[0].checkbox("Close > EMA10", key="sc_c10",
                                   value=bool(cfg_s.get("close_above_ema10")))
            f_c20 = f4[1].checkbox("Close > EMA20", key="sc_c20",
                                   value=bool(cfg_s.get("close_above_ema20")))
            f_stack = f4[2].checkbox("EMA10 + EMA20 ueber SMA50", key="sc_stack",
                                     value=bool(cfg_s.get("ema10_20_above_sma50")))

        res = snap.copy()
        m = pd.Series(True, index=res.index)

        def rng(col, lo, hi, scale=1.0):
            global m
            if lo is not None:
                m &= res[col] >= lo * scale
            if hi is not None:
                m &= res[col] <= hi * scale

        if f_uni:
            um = pd.Series(False, index=res.index)
            for lbl, col in (("S&P 500", "SP500"), ("Nasdaq", "NASDAQ"),
                             ("Russell 2000", "R2000")):
                if lbl in f_uni:
                    um |= res[col].astype(bool)
            m &= um
        if f_sec:
            m &= res["Sector"].isin(f_sec)
        rng("RS", f_rs, None)
        rng("Price", f_price, None)
        rng("MarketCap", f_cap, None, 1e6)
        rng("AVOL", f_avol, None, 1e3)
        rng("RVOL", f_rvol, None)
        rng("ATR%", f_atr_lo, f_atr_hi)
        rng("Gain50%", f_g50_lo, f_g50_hi)
        rng("ATRx50", f_ax_lo, f_ax_hi)
        if f_c10:
            m &= res["Price"] > res["EMA10"]
        if f_c20:
            m &= res["Price"] > res["EMA20"]
        if f_stack:
            m &= (res["EMA10"] > res["SMA50"]) & (res["EMA20"] > res["SMA50"])
        if f_trend == "stage2":
            m &= res["Stage"] == 2
        elif f_trend == "sma50_above_sma200":
            m &= res["SMA50"] > res["SMA200"]
        elif f_trend == "above_sma200":
            m &= res["Price"] > res["SMA200"]
        res = res[m].copy()

        # "Neu" = heute in der gespeicherten Scanner-Liste, gestern nicht
        hist_s = load_scan_history()
        new_set = set()
        if not hist_s.empty:
            days_s = sorted(hist_s["date"].unique())
            today_hits = set(hist_s.loc[hist_s["date"] == days_s[-1], "Ticker"])
            prev_hits = (set(hist_s.loc[hist_s["date"] == days_s[-2], "Ticker"])
                         if len(days_s) > 1 else set())
            new_set = today_hits - prev_hits
        res.insert(1, "Neu", res["Ticker"].map(lambda t: "★" if t in new_set else ""))

        res = res.sort_values(["RS", "Gain50%"], ascending=False).reset_index(drop=True)
        view = pd.DataFrame({
            "Ticker": res["Ticker"], "Neu": res["Neu"], "Name": res["Name"],
            "Sektor": res["Sector"], "Branche": res["Industry"],
            "Cap Mrd $": res["MarketCap"] / 1e9, "Kurs": res["Price"],
            "1D %": res["Chg%"], "ATR%": res["ATR%"], "Gain MA50 %": res["Gain50%"],
            "ATRx MA50": res["ATRx50"], "AVOL Mio": res["AVOL"] / 1e6,
            "RVOL": res["RVOL"], "RS": res["RS"].astype("Int64"),
            "Stage": res["Stage"].astype("Int64"), "1M %": res["Perf1M%"],
            "3M %": res["Perf3M%"], "vom Hoch %": res["FromHigh%"],
        })

        def col_atrx(v):
            if pd.isna(v):
                return ""
            if v > 4:
                return "background-color: rgba(224,90,90,0.65); color: #fff"
            if v < 0:
                return "color: #9fb0e8"
            return ""

        def col_rvol_s(v):
            if pd.isna(v):
                return ""
            return ("background-color: rgba(63,224,160,0.75); color: #fff"
                    if v >= 1.5 else "")

        st.markdown(f"**{len(view)} Treffer** von {len(snap)} Titeln"
                    + (f" · ★ neu in der gespeicherten Liste: {len(new_set)}"
                       if new_set else ""))
        ev_s = st.dataframe(
            view.style
            .map(col_pct, subset=["1D %", "1M %", "3M %"])
            .map(col_atrx, subset=["ATRx MA50"])
            .map(col_rvol_s, subset=["RVOL"])
            .format({"Cap Mrd $": "{:,.2f}", "Kurs": "{:,.2f}", "1D %": "{:+.2f}",
                     "ATR%": "{:.2f}", "Gain MA50 %": "{:+.1f}",
                     "ATRx MA50": "{:+.2f}", "AVOL Mio": "{:.2f}",
                     "RVOL": "{:.2f}", "1M %": "{:+.1f}", "3M %": "{:+.1f}",
                     "vom Hoch %": "{:+.1f}"}, na_rep="–"),
            use_container_width=True, hide_index=True,
            height=min(42 + 35 * len(view), 900), key="scan_table",
            on_select="rerun", selection_mode="single-row")
        try:
            sel_rows = ev_s["selection"]["rows"]
        except (TypeError, KeyError):
            sel_rows = []
        if sel_rows:
            sym_s = str(view.iloc[sel_rows[0]]["Ticker"])
            render_detail_chart(sym_s, str(view.iloc[sel_rows[0]]["Name"]))

        ex1, ex2 = st.columns(2)
        with ex1:
            st.download_button("Treffer als CSV", view.to_csv(index=False),
                               file_name="scanner_treffer.csv", mime="text/csv")
            tv = ",".join(f"{e}:{t}" for e, t in zip(res["Exchange"], res["Ticker"])
                          if e in ("NASDAQ", "NYSE", "AMEX"))
            st.text_area("TradingView-Watchlist (kopieren & importieren)", tv,
                         height=90)
        with ex2:
            new_cfg = {
                "min_price": f_price, "min_market_cap": f_cap * 1e6 if f_cap else None,
                "min_avol": f_avol * 1e3 if f_avol else None, "min_rvol": f_rvol,
                "min_atr_pct": f_atr_lo, "max_atr_pct": f_atr_hi,
                "min_gain50": f_g50_lo, "max_gain50": f_g50_hi,
                "min_atrx50": f_ax_lo, "max_atrx50": f_ax_hi,
                "close_above_ema10": f_c10, "close_above_ema20": f_c20,
                "ema10_20_above_sma50": f_stack, "trend": f_trend,
            }
            if st.button("Filter als Scanner-Liste speichern", type="primary"):
                import json as _json
                with open(SCANNER_CONFIG, "w", encoding="utf-8") as f:
                    _json.dump({"_hinweis": "Scanner-Kriterien fuer die eigene "
                                "Universumsliste. null = Filter aus.", **new_cfg},
                               f, indent=2)
                st.success("scanner_config.json gespeichert – gilt ab dem "
                           "naechsten Datenlauf.")
            st.caption("Lokal wird die Datei direkt gespeichert. In der Cloud "
                       "ist das Dateisystem fluechtig: dort den Inhalt unten in "
                       "scanner_config.json im GitHub-Repo einfuegen. RS-Filter "
                       "und Index/Sektor wirken nur hier in der Ansicht.")
            import json as _json
            st.code(_json.dumps(new_cfg, indent=2), language="json")

        st.caption(
            f"Stand {load_data_meta().get('last_date', '?')} · ATR% = ATR14/Kurs · "
            "Gain MA50 = Abstand zum SMA50 · ATRx MA50 = Gain MA50 / ATR% "
            "(rot > 4 = ueberdehnt) · AVOL = Ø Volumen 50T · RVOL = Volumen / "
            "AVOL · RS = IBD-Stil gegen alle ~4.400 Titel · ★ = neu in der "
            "gespeicherten Scanner-Liste.")

# ----- Tab: Index-Maps (Finviz-Stil) -----
INDEX_FILES = {
    "S&P 500 (All Stocks)": ("idx_sp500.csv", True),
    "Nasdaq 100": ("idx_nasdaq100.csv", True),
    "Dow Jones 30": ("idx_dow.csv", False),
    "Small Caps (S&P 600 als Russell-Proxy)": ("idx_smallcap.csv", True),
}

@st.cache_data(ttl=600, show_spinner=False)
def fetch_index_ohlcv(tickers: tuple) -> tuple:
    """Closes + Volumen fuer eine Index-Konstituentenliste (10 min Cache).
    Wichtig: ohne Cache wuerde Streamlit diesen Download bei JEDEM Rerun
    ausfuehren (alle Tab-Bloecke laufen pro Interaktion)."""
    d = bulk_download(list(tickers), "6mo")
    closes = d.get("Close", pd.DataFrame()).dropna(how="all")
    return closes, d.get("Volume")


with tab_idx:
    col_sel, col_tf = st.columns([2, 3])
    with col_sel:
        idx_choice = st.selectbox("Index", list(INDEX_FILES.keys()),
                                  label_visibility="collapsed")
    with col_tf:
        tfi = st.radio("Zeitfenster", list(TIMEFRAMES.keys()), horizontal=True,
                       label_visibility="collapsed", key="tf_idx")

    fname, use_industry = INDEX_FILES[idx_choice]
    fpath = os.path.join(BASE, fname)
    if not os.path.exists(fpath):
        st.error(f"{fname} fehlt im App-Ordner.")
    elif not st.session_state.get("idx_on"):
        st.button("Index-Map laden (S&P 500 / Small Caps: ~1-2 Min beim "
                  "ersten Mal, danach 10 min gecacht)", key="idx_btn",
                  on_click=lambda: st.session_state.update(idx_on=True))
    else:
        idx_uni = pd.read_csv(fpath)
        idx_uni["Ticker"] = idx_uni["Ticker"].astype(str).str.upper().str.strip()
        n_titles = len(idx_uni)
        with st.spinner(f"Lade {n_titles} Titel..."):
            closes_i, vol_i = fetch_index_ohlcv(tuple(idx_uni["Ticker"]))

        chg_i = compute_changes(closes_i)
        dfi = idx_uni.merge(chg_i, left_on="Ticker", right_index=True,
                            how="left").dropna(subset=[tfi])
        if dfi.empty:
            st.error("Keine Kursdaten geladen.")
        else:
            # Kachelgroesse: Dollar-Volumen (20 Tage) statt Market Cap –
            # aus demselben Download berechenbar, kein Extra-Abruf pro Titel.
            if vol_i is not None:
                dv = (closes_i.iloc[-20:] * vol_i.iloc[-20:]).mean()
                dfi["Size"] = np.sqrt(dfi["Ticker"].map(dv).fillna(dv.median())
                                      .clip(lower=1))
            else:
                dfi["Size"] = 1.0

            limit_i = TIMEFRAMES[tfi][1]
            path = ([px.Constant("Alle"), "Sector", "Industry", "Ticker"]
                    if use_industry and "Industry" in dfi.columns
                    else [px.Constant("Alle"), "Sector", "Ticker"])
            dfi["ShortName"] = dfi["Name"].astype(str).str.slice(0, 28)

            figi = px.treemap(
                dfi, path=path, values="Size", color=tfi,
                color_continuous_scale=COLOR_SCALE,
                range_color=(-limit_i, limit_i),
                custom_data=["Last", "1D", "1W", "2W", "4W", "Ticker", "Name"],
            )
            idxp = list(TIMEFRAMES.keys()).index(tfi) + 1
            figi.update_traces(
                texttemplate="<b>%{label}</b><br>%{customdata["
                             + str(idxp) + "]:.2f} %",
                textposition="middle center",
                hovertemplate=(
                    "<b>%{customdata[5]}</b> · %{customdata[6]}<br>"
                    "Kurs: %{customdata[0]:,.2f}<br>"
                    "1D: %{customdata[1]:.2f} % · 1W: %{customdata[2]:.2f} %<br>"
                    "2W: %{customdata[3]:.2f} % · 4W: %{customdata[4]:.2f} %"
                    "<extra></extra>"
                ),
                marker=dict(line=dict(width=0.7, color=NAVY_BG)),
            )
            figi.update_layout(
                margin=dict(t=10, l=0, r=0, b=0), height=760,
                paper_bgcolor=NAVY_BG,
                font=dict(family="Arial, sans-serif", color="#ffffff"),
                coloraxis_colorbar=dict(title="%",
                                        tickfont=dict(color="#ffffff")),
            )
            st.caption("Tipp: Kachel anklicken -> Detail-Chart. Sektor-Kopf "
                       "anklicken -> Zoom in den Sektor, 'Alle' oben fuehrt "
                       "zurueck.")
            evi = st.plotly_chart(figi, use_container_width=True, key="map_idx",
                                  on_select="rerun", selection_mode="points")
            try:
                ipts = evi["selection"]["points"]
            except (TypeError, KeyError):
                ipts = []
            if ipts:
                lab = ipts[0].get("label")
                hit = dfi[dfi["Ticker"] == lab]
                if not hit.empty:
                    render_detail_chart(lab, hit["Name"].iloc[0])
            st.caption(
                f"{idx_choice} · {len(dfi)} Titel · Kachelgroesse = "
                f"Dollar-Volumen (20T-Schnitt), nicht Market Cap · "
                f"Stand: {closes_i.index[-1]:%Y-%m-%d} · Quelle: Yahoo. "
                f"Konstituenten via Wikipedia-Listen (idx_*.csv, editierbar)."
            )

# ----- Tab 6: Theme Tracker -----
TT_WINDOWS = {"1D": 1, "1W": 5, "1M": 21, "3M": 63, "YTD": None}

with tab_themes:
    ttf = st.radio("Zeitraum", list(TT_WINDOWS.keys()), horizontal=True,
                   label_visibility="collapsed", key="tf_themes")
    uni_t = load_csv(TICKER_FILE)
    if uni_t.empty:
        st.warning("Universum leer.")
    else:
        with st.spinner("Lade Themes..."):
            closes_t = fetch_closes(tuple(uni_t["Ticker"]), period="1y")

        # % Change je Ticker fuer das gewaehlte Fenster
        chg_t = {}
        for col in closes_t.columns:
            s = closes_t[col].dropna()
            if s.empty:
                continue
            n = TT_WINDOWS[ttf]
            if n is None:                     # YTD: letzter Close des Vorjahres
                base = s[s.index.year < s.index[-1].year]
                if base.empty:
                    continue
                chg_t[col] = (s.iloc[-1] / base.iloc[-1] - 1) * 100
            elif len(s) > n:
                chg_t[col] = (s.iloc[-1] / s.iloc[-(n + 1)] - 1) * 100
        perf = pd.Series(chg_t, name="chg")

        # Theme-Performance = Durchschnitt der zugehoerigen ETFs
        dft = uni_t.merge(perf, left_on="Ticker", right_index=True)
        theme_perf = (dft.groupby("Theme")["chg"].mean()
                      .sort_values(ascending=True))   # ascending: Top oben im Chart

        import plotly.graph_objects as go
        colors = [MINT if v >= 0 else "#ff5fa2" for v in theme_perf.values]
        figt = go.Figure(go.Bar(
            x=theme_perf.values, y=theme_perf.index, orientation="h",
            marker_color=colors,
            text=[f"{v:+.2f} %" for v in theme_perf.values],
            textposition="outside",
            textfont=dict(color="#fff", size=12),
        ))
        pad = max(abs(theme_perf.min()), abs(theme_perf.max())) * 0.25 + 0.5
        figt.update_layout(
            title=dict(text=f"Theme Tracker · {ttf} · Durchschnitt der "
                            "Theme-ETFs", font=dict(size=15, color="#fff")),
            height=32 * len(theme_perf) + 90,
            margin=dict(t=45, l=0, r=10, b=0),
            paper_bgcolor=NAVY_BG, plot_bgcolor=NAVY_BG,
            font=dict(color="#fff"),
            xaxis=dict(gridcolor="#243063", zerolinecolor="#4a5a8a",
                       range=[theme_perf.min() - pad, theme_perf.max() + pad],
                       ticksuffix=" %"),
            yaxis=dict(gridcolor="rgba(0,0,0,0)"),
            showlegend=False, bargap=0.25,
        )
        st.caption("Tipp: Balken anklicken -> ETFs des Themes erscheinen darunter.")
        evt = st.plotly_chart(figt, use_container_width=True, key="theme_bars",
                              on_select="rerun", selection_mode="points")
        try:
            tpts = evt["selection"]["points"]
        except (TypeError, KeyError):
            tpts = []
        if tpts:
            sel_theme = tpts[0].get("y")
            members = (dft[dft["Theme"] == sel_theme]
                       [["Ticker", "Name", "chg"]]
                       .sort_values("chg", ascending=False)
                       .rename(columns={"chg": f"{ttf} %"}))
            st.markdown(f"**{sel_theme}** – Einzel-ETFs ({ttf}):")
            st.dataframe(
                members.style
                .map(lambda v: col_pct(v) if isinstance(v, float) else "",
                     subset=[f"{ttf} %"])
                .format({f"{ttf} %": "{:+.2f} %"}),
                use_container_width=True, hide_index=True,
            )
        st.caption(
            f"Stand: {closes_t.index[-1]:%Y-%m-%d} · Quelle: Yahoo (~15 min) · "
            "Sortiert nach Performance. YTD = seit letztem Handelstag des "
            "Vorjahres."
        )

# ----- Tab: Kalender (US-Makro, Quelle: Concretum) -----
CAL_BASE = "https://calendar.concretumgroup.com/api"


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_cal_catalog() -> list:
    import urllib.request, json as _json
    req = urllib.request.Request(CAL_BASE + "/events/catalog/",
                                 headers={"User-Agent": "Mozilla/5.0"})
    return _json.loads(urllib.request.urlopen(req, timeout=15).read())["events"]


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_cal_events(codes: tuple, days: int) -> pd.DataFrame:
    import urllib.request, json as _json, datetime as _dt
    start = _dt.date.today()
    end = start + _dt.timedelta(days=days)
    url = (f"{CAL_BASE}/events/preview/?events={','.join(codes)}"
           f"&start={start}&end={end}&layout=long"
           f"&include_assumed_time=true&ordering=event_date&page_size=200")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    rows = _json.loads(urllib.request.urlopen(req, timeout=15).read())["rows"]
    return pd.DataFrame(rows)


with tab_cal:
    try:
        catalog = fetch_cal_catalog()
    except Exception as e:
        catalog = []
        st.error(f"Kalender-Quelle nicht erreichbar ({e}).")
    if catalog:
        code2name = {e["event_code"]: e["event_name"] for e in catalog}
        default_codes = [c for c in ["fomc", "cpi", "nfp", "pce", "gdp",
                                     "ppi", "retail", "claims"]
                         if c in code2name]
        ccol1, ccol2 = st.columns([3, 1])
        with ccol1:
            sel = st.multiselect("Events", list(code2name.keys()),
                                 default=default_codes,
                                 format_func=lambda c: code2name[c],
                                 label_visibility="collapsed")
        with ccol2:
            horizon = st.selectbox("Zeitraum", [14, 30, 60, 90], index=2,
                                   format_func=lambda d: f"{d} Tage",
                                   label_visibility="collapsed")
        if sel:
            with st.spinner("Lade Kalender..."):
                ev = fetch_cal_events(tuple(sorted(sel)), int(horizon))
            if ev.empty:
                st.info("Keine Events im Zeitraum.")
            else:
                from zoneinfo import ZoneInfo
                ev["event_date"] = pd.to_datetime(ev["event_date"])
                today = pd.Timestamp.today().normalize()
                ev["In Tagen"] = (ev["event_date"] - today).dt.days

                def de_time(row):
                    t = row["assumed_time_et"]
                    if not t:
                        return "–"
                    et = pd.Timestamp(f"{row['event_date'].date()} {t}",
                                      tz="America/New_York")
                    return et.tz_convert("Europe/Berlin").strftime("%H:%M")

                ev["Zeit ET"] = ev["assumed_time_et"].replace("", "–")
                ev["Zeit DE"] = ev.apply(de_time, axis=1)
                ev["Datum"] = ev["event_date"].dt.strftime("%a %d.%m.%Y")
                ev["Zeit best."] = ev["time_verified"].map(
                    {True: "ja", False: "angenommen"})
                out = ev[["Datum", "In Tagen", "event_name", "Zeit ET",
                          "Zeit DE", "Zeit best."]].rename(
                    columns={"event_name": "Event"})

                def row_hl(row):
                    if row["In Tagen"] <= 1:
                        return ["background-color: rgba(63,224,160,0.25)"] \
                            * len(row)
                    if row["In Tagen"] <= 7:
                        return [f"background-color: {NAVY_CARD}"] * len(row)
                    return [""] * len(row)

                st.dataframe(out.style.apply(row_hl, axis=1),
                             use_container_width=True, hide_index=True,
                             height=42 + 35 * len(out))
                nxt = out.iloc[0]
                st.caption(
                    f"Naechstes Event: {nxt['Event']} am {nxt['Datum']} "
                    f"({nxt['Zeit DE']} Uhr DE) · Gruen = heute/morgen, "
                    f"dunkel = diese Woche · 'angenommen' = Uhrzeit noch "
                    f"nicht offiziell bestaetigt · Quelle: "
                    f"calendar.concretumgroup.com (Concretum Group)."
                )

# ----- Tab: Gate-Check (Pre-Trade Go/No-Go, Master Playbook Teil 3) -----
GATE_SECTIONS = [
    ("A", "Markt-Gates", "hart", [
        ("A1", "Leitindex (QQQ/SPY) <= 4x ATR-Extension vom 50-MA",
         "Jeffs SPY-Regel · Verbotszone 4"),
        ("A2", "Regime-Leiter-Tier erlaubt neues Risiko (Exposure-Budget frei)",
         "Regime-Leiter v2 + Puffer-Gate"),
        ("A3", "Kein aktives S1-Schutzregime gegen die Trade-Richtung",
         "Regel S1-S3"),
    ]),
    ("B", "Aktien-Gates", "hart", [
        ("B1", "Ticker-Zustand erlaubt Entry (SCHARF/TRIGGERED bzw. RO-Trigger "
               "- nicht Digestion, nicht Fruehwarnung)",
         "Zustandsmaschine · Verbotszone 6/12"),
        ("B2", "Kein SPHR-Typ: <= 4 Closes unter 10-MA in 20 Tagen (P2: <= 2)",
         "Regel Q1/Q2 · Verbotszone 7"),
        ("B3", "ATR valide - kein Buyout-Pin/ATR-Kollaps (ATR% > 0,5 % des Kurses)",
         "ATR-Floor G6"),
    ]),
    ("C", "Setup-Gates", "hart", [
        ("C1", "ATR-Ext <= 4x (SmallCap < 500M: <= 5x) - oder Kontext-Schalter "
               "qualifiziert & dokumentiert (RO-Play)",
         "Regel E1 · G4 · Verbotszone 1"),
        ("C2", "ZVR / at-Time-RVOL > 100 % - Volumen bestaetigt JETZT",
         "Concretum Fig. 4 · Verbotszone 2"),
        ("C3", "Pivot/Struktur klar definiert (Kompression davor, Level benennbar)",
         "Regel E3 · KC Schritt 3"),
    ]),
    ("D", "Intraday-Gates", "hart", [
        ("D1", "LoD dist. < 50-60 % 'at time' - bei Buy-Stop: "
               "(Entry-Stop) / ATR < 50 %", "Regel E2 · Verbotszone 3"),
        ("D2", "Innerhalb des Execution-Fensters (erste 90 Min)",
         "Zeitverfall Paper 2/3 · Verbotszone 8"),
    ]),
    ("E", "Risiko-Gates", "hart", [
        ("E1", "Stop <= 1 ATR vom Entry", "Regel E1/K"),
        ("E2", "Risiko <= 0,25 % (0,33 % nur wenn M3 gruen: Regime oben + "
               "PF > 3 + unter Kelly-Deckel)", "K3 · M3 · M5 · Journal-Blatt"),
        ("E3", "Groesse aus Spreadsheet; Kapitalbindung im Budget; "
               "Position <= 1 % Ø-$-Tagesvolumen",
         "K1/K2 · Liquidity-Cap · Verbotszone 10"),
    ]),
    ("F", "Selbst-Gates", "weich", [
        ("F1", "Verlustserie < 20 (Aufmerksamkeitszone) - sonst Risiko 0,15 %, "
               "Frequenz drosseln", "M1 · Monte-Carlo-Baender"),
        ("F2", "Kein Revenge/FOMO - Trade stand vor heute auf der Liste bzw. "
               "kommt aus Screen B ∩ SCHARF",
         "'Earn your next trade' · Verbotszone 12"),
        ("F3", "Setup-Tag vergeben & T+3-Datum notiert, Management-Alerts "
               "vorbereitet", "Journal-Tagging · T+3-Protokoll"),
    ]),
]
SETUPS = ["P1 - Kompressions-Breakout", "P2 - Trendfolge-Pullback",
          "KC - Charakterwechsel", "RO - Repeat-Offender-Slingshot",
          "S - Schutz/Short-Modul"]
HARD_TOTAL = sum(len(g) for _, _, t, g in GATE_SECTIONS if t == "hart")
SOFT_TOTAL = sum(len(g) for _, _, t, g in GATE_SECTIONS if t == "weich")


@st.cache_data(ttl=QUOTE_TTL, show_spinner=False)
def atr_ext_50ma(ticker: str) -> float:
    """ATR-Extension vom 50-MA: (Close - SMA50) / ATR14."""
    d = fetch_ohlc(ticker, period="6mo")
    if d.empty or len(d) < 60:
        return float("nan")
    c, h, l = d["Close"], d["High"], d["Low"]
    tr = pd.concat([h - l, (h - c.shift()).abs(),
                    (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1]
    sma50 = c.rolling(50).mean().iloc[-1]
    return float((c.iloc[-1] - sma50) / atr) if atr else float("nan")


with tab_gate:
    st.caption("Vor jeder Order. Hartes Gate offen = NO-GO, weiche offen = "
               "Vorsicht. Keine Speicherung - jeder Trade wird frisch geprueft.")
    g1, g2, g3 = st.columns([1, 2, 1])
    with g1:
        gt_ticker = st.text_input("Ticker", key="gate_ticker",
                                  placeholder="z.B. PANW").upper().strip()
    with g2:
        gt_setup = st.selectbox("Setup-Tag", ["—"] + SETUPS, key="gate_setup")
    with g3:
        gt_dir = st.selectbox("Richtung", ["Long", "Short"], key="gate_dir")

    # --- Live-Vorpruefung aus vorhandenen Daten ---
    hints = {}
    try:
        spy_ext = atr_ext_50ma("SPY")
        qqq_ext = atr_ext_50ma("QQQ")
        worst = max(abs(spy_ext), abs(qqq_ext))
        hints["A1"] = (worst <= 4,
                       f"SPY {spy_ext:+.1f}x · QQQ {qqq_ext:+.1f}x vom 50-MA")
    except Exception:
        pass
    if gt_ticker:
        try:
            sg = fetch_signals((gt_ticker,))
            if not sg.empty:
                rv = sg.iloc[0]["RVOL_live"]
                rv = sg.iloc[0]["RVOL_prev"] if pd.isna(rv) else rv
                ext = atr_ext_50ma(gt_ticker)
                hints["C2"] = (rv > 1.0, f"{gt_ticker} RVOL {rv:.2f}")
                hints["C1"] = (abs(ext) <= 4,
                               f"{gt_ticker} ATR-Ext {ext:+.1f}x vom 50-MA")
        except Exception:
            pass
    if hints:
        st.caption("Live-Vorpruefung (ersetzt nicht den Haken - die Zahl ist "
                   "~15 min verzoegert): "
                   + " · ".join(f"{'✓' if ok else '✗'} {k}: {txt}"
                                for k, (ok, txt) in sorted(hints.items())))

    # --- Gate-Liste ---
    checked = {}
    cols = st.columns(2)
    for i, (sid, title, typ, gates) in enumerate(GATE_SECTIONS):
        with cols[i % 2]:
            st.markdown(f"**{sid} · {title}** "
                        f"<span style='color:#9fb0e8;font-size:11px'>({typ})</span>",
                        unsafe_allow_html=True)
            for gid, text, ref in gates:
                hint = hints.get(gid)
                mark = "" if hint is None else ("  ✓" if hint[0] else "  ✗")
                checked[gid] = st.checkbox(f"**{gid}** {text}{mark}",
                                           key=f"gate_{gid}")
                st.caption(ref)
            st.write("")

    hard_ok = sum(1 for sid, _, t, g in GATE_SECTIONS if t == "hart"
                  for gid, _, _ in g if checked.get(gid))
    soft_ok = sum(1 for sid, _, t, g in GATE_SECTIONS if t == "weich"
                  for gid, _, _ in g if checked.get(gid))
    open_gates = [gid for _, _, _, g in GATE_SECTIONS
                  for gid, _, _ in g if not checked.get(gid)]

    if hard_ok < HARD_TOTAL:
        verdict, vcol = "NO-GO", "#e05a5a"
        detail = f"{HARD_TOTAL - hard_ok} hartes Gate offen – kein Trade."
    elif soft_ok < SOFT_TOTAL:
        verdict, vcol = "VORSICHT", "#ffd166"
        detail = (f"Alle harten Gates gruen, {SOFT_TOTAL - soft_ok} weiches "
                  "offen – Size reduzieren oder Begruendung ins Journal.")
    else:
        verdict, vcol = "GO", MINT
        detail = "Alle Gates gruen. Ausfuehren – Groesse kommt aus dem Spreadsheet."

    st.markdown(
        f"<div style='background:#10182f;border:2px solid {vcol};"
        f"border-radius:10px;padding:14px 18px;margin-top:6px'>"
        f"<span style='color:{vcol};font-weight:900;font-size:22px'>{verdict}</span>"
        f"<span style='color:#cfd6f0;margin-left:14px'>hart {hard_ok}/{HARD_TOTAL}"
        f" · weich {soft_ok}/{SOFT_TOTAL}</span>"
        f"<div style='color:#9fb0e8;font-size:13px;margin-top:6px'>{detail}</div>"
        f"</div>", unsafe_allow_html=True)

    now_de = pd.Timestamp.now(tz="Europe/Berlin")
    line = (f"{now_de:%d.%m.%Y %H:%M} | {gt_ticker or '—'} | "
            f"{gt_setup} | {gt_dir} | Gate-Check: {verdict} "
            f"(hart {hard_ok}/{HARD_TOTAL}, weich {soft_ok}/{SOFT_TOTAL})"
            + (f" | offen: {','.join(open_gates)}" if open_gates else ""))
    st.text_input("Journal-Zeile (kopierbar)", value=line, key="gate_line")

# ----- Tab 7: Universum -----
with tab_universe:
    st.caption("Aktien/ETF-Universum (tickers.csv) – Yahoo-Notation, Zeilen via + hinzufuegen.")
    edited = st.data_editor(load_csv(TICKER_FILE), num_rows="dynamic",
                            use_container_width=True, key="ed_stocks")
    if st.button("Aktien/ETF speichern", type="primary"):
        save_csv(edited, TICKER_FILE)
        st.cache_data.clear()
        st.success("Gespeichert.")
    st.divider()
    st.caption("Generaele-Baskets (generals.csv) – Spalten: Ticker, Sektor, "
               "EW_ETF (Equal-Weight-Vergleichs-ETF des Sektors).")
    edited_g = st.data_editor(pd.read_csv(GENERALS_FILE)
                              if os.path.exists(GENERALS_FILE)
                              else pd.DataFrame(columns=["Ticker", "Sektor",
                                                         "EW_ETF"]),
                              num_rows="dynamic", use_container_width=True,
                              key="ed_gen")
    if st.button("Generaele speichern"):
        edited_g.to_csv(GENERALS_FILE, index=False)
        st.cache_data.clear()
        st.success("Gespeichert.")
    st.divider()
    st.caption("Futures/Makro-Universum (futures.csv).")
    edited_f = st.data_editor(load_csv(FUTURES_FILE), num_rows="dynamic",
                              use_container_width=True, key="ed_fut")
    if st.button("Futures speichern"):
        save_csv(edited_f, FUTURES_FILE)
        st.cache_data.clear()
        st.success("Gespeichert.")
