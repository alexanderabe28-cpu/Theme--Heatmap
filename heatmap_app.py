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


@st.cache_data(ttl=RS_TTL, show_spinner=False)
def fetch_universe_ohlcv(extra_symbols: tuple) -> dict:
    """OHLCV fuer das S&P-500-Universum (+ Watchlist). Ein Download fuer
    RS-Rating UND Breadth-Panel."""
    try:
        uni = pd.read_csv(RS_UNIVERSE_FILE)["Ticker"].astype(str).tolist()
    except Exception:
        uni = []
    symbols = sorted(set(uni) | {s.upper() for s in extra_symbols})
    raw = yf.download(symbols, period="18mo", auto_adjust=True,
                      progress=False, group_by="column", threads=True)
    out = {}
    for field in ["Open", "High", "Low", "Close", "Volume"]:
        if field in raw:
            df = raw[field]
            if isinstance(df, pd.Series):
                df = df.to_frame(name=symbols[0])
            out[field] = df
    return out


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
                     progress=False, group_by="column")
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
    raw = yf.download(list(tickers), period="4mo", auto_adjust=True,
                      progress=False, group_by="column", threads=True)
    C = raw["Close"]; H = raw["High"]; L = raw["Low"]; V = raw["Volume"]
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
 tab_themes, tab_cal, tab_universe) = st.tabs(
    ["Aktien / ETF", "Index-Maps", "Futures / Makro", "Watchlist", "OvsD",
     "Generaele", "Breadth", "Theme Tracker", "Kalender", "Universum"])

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


with tab_breadth:
    st.caption(
        "Marktbreite gegen das S&P-500-Universum (rs_universe.csv) – "
        "Proxy fuer den Gesamtmarkt, Stand letzter Handelstag."
    )
    if not st.session_state.get("breadth_on"):
        st.button("Breadth berechnen (~2 Min beim ersten Mal, teilt sich den "
                  "Download mit IBD-RS)", key="breadth_btn",
                  on_click=lambda: st.session_state.update(breadth_on=True))
    else:
        wl_now = load_csv(WATCHLIST_FILE) if os.path.exists(WATCHLIST_FILE) \
            else pd.DataFrame(columns=["Ticker"])
        with st.spinner("Berechne Marktbreite..."):
            b = compute_breadth(tuple(wl_now["Ticker"]))
        if not b:
            st.error("Breadth-Daten unvollstaendig – Universum pruefen.")
        else:
            row1 = (
                breadth_card("Advancing", "Declining", b["adv"], b["dec"])
                + breadth_card("New High", "New Low", b["nh"], b["nl"])
                + breadth_card("Above", "Below", b["ab50"], b["bl50"], "SMA50")
                + breadth_card("Above", "Below", b["ab200"], b["bl200"],
                               "SMA200")
            )
            st.markdown(
                f"<div style='display:flex;gap:10px;flex-wrap:wrap'>{row1}</div>",
                unsafe_allow_html=True)
            row2 = (
                breadth_card("Up from Open", "Down from Open",
                             b.get("up_open", 0), b.get("dn_open", 0))
                + breadth_card("Up on Volume", "Down on Volume",
                               b.get("up_vol", 0), b.get("dn_vol", 0))
                + breadth_card("Up 4%", "Down 4%", b["up4"], b["dn4"])
            )
            st.markdown(
                f"<div style='display:flex;gap:10px;flex-wrap:wrap;"
                f"margin-top:10px'>{row2}</div>",
                unsafe_allow_html=True)

            # Stage-Analyse als gestapelter Balken
            s1, s2_, s3, s4 = b["stages"]
            tot = max(s1 + s2_ + s3 + s4, 1)
            seg = lambda n, col: (f"<div style='background:{col};"
                                  f"width:{n/tot*100:.1f}%;height:100%'></div>")
            st.markdown(
                f"""<div style="margin:18px 0 4px">
                <span style="color:#fff;font-weight:800">Stage Analysis
                (Weinstein-Naeherung, SMA200)</span>
                <div style="display:flex;background:#243063;border-radius:6px;
                            height:12px;overflow:hidden;margin:8px 0">
                  {seg(s1, "#8a93b8")}{seg(s2_, "#4da3ff")}
                  {seg(s3, "#ffd166")}{seg(s4, "#ff5fa2")}
                </div>
                <div style="display:flex;gap:22px;font-size:13px;flex-wrap:wrap">
                  <span style="color:#8a93b8">● Stage 1 (Boden):
                    <b>{s1}</b> · {s1/tot*100:.0f} %</span>
                  <span style="color:#4da3ff">● Stage 2 (Aufwaertstrend):
                    <b>{s2_}</b> · {s2_/tot*100:.0f} %</span>
                  <span style="color:#ffd166">● Stage 3 (Top):
                    <b>{s3}</b> · {s3/tot*100:.0f} %</span>
                  <span style="color:#ff5fa2">● Stage 4 (Abwaertstrend):
                    <b>{s4}</b> · {s4/tot*100:.0f} %</span>
                </div></div>""",
                unsafe_allow_html=True,
            )
            st.caption(
                f"Universum: {b['n']} Titel · Stand: {b['date']} · "
                "Up/Down on Volume = Tagesrichtung bei Volumen ueber dem "
                "50-Tage-Schnitt · NH/NL = 252-Tage-Extreme."
            )

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
    raw = yf.download(list(tickers), period="6mo", auto_adjust=True,
                      progress=False, group_by="column", threads=True)
    closes = raw["Close"].dropna(how="all")
    vol = raw["Volume"] if "Volume" in raw else None
    return closes, vol


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
