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


# ---------------- Universen laden / speichern ----------------
def load_csv(path: str) -> pd.DataFrame:
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
                   label_col: str = "Ticker") -> str | None:
    """Zeichnet die Treemap und gibt den angeklickten Ticker zurueck (oder None)."""
    df = df.copy()
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
        custom_data=["Last", "1D", "1W", "2W", "4W", "Ticker", "ShortName", "Name"],
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
            "4W: %{customdata[4]:.2f} %<extra></extra>"
        ),
        marker=dict(line=dict(width=1.5, color=NAVY_BG)),
    )
    fig.update_layout(
        margin=dict(t=10, l=0, r=0, b=0),
        height=680,
        paper_bgcolor=NAVY_BG,
        font=dict(family="Arial Black, Arial, sans-serif", color="#ffffff"),
        coloraxis_colorbar=dict(title="%", tickfont=dict(color="#ffffff")),
    )
    st.caption("Tipp: Kachel anklicken -> Detail-Chart erscheint darunter.")
    event = st.plotly_chart(fig, use_container_width=True, key=key,
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

(tab_map, tab_fut, tab_watch, tab_ovsd, tab_breadth, tab_themes,
 tab_universe) = st.tabs(
    ["Aktien / ETF", "Futures / Makro", "Watchlist", "OvsD", "Breadth",
     "Theme Tracker", "Universum"])

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
        df = prepare(universe, closes, sizes, tf)
        if df.empty:
            st.error("Keine Kursdaten – Ticker pruefen.")
        else:
            limit = TIMEFRAMES[tf][1]
            picked = render_treemap(df, tf, limit, key="map_stocks")
            st.caption(
                f"{tf} = letzter Kurs vs. Close vor {TIMEFRAMES[tf][0]} Handelstag(en) · "
                f"Skala ±{limit:.0f} % · Stand: {closes.index[-1]:%Y-%m-%d} · "
                f"Quelle: {'IBKR' if use_ibkr else 'Yahoo (~15 min)'}"
            )
            if picked:
                nm = df[df["Ticker"] == picked]["Name"]
                render_detail_chart(picked, nm.iloc[0] if len(nm) else picked)

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
        picked_o = render_treemap(dfo, tfo, limit_o, key="map_ovsd",
                                  label_col="Name")
        if picked_o:
            nm = dfo[dfo["Ticker"] == picked_o]["Name"]
            render_detail_chart(picked_o, nm.iloc[0] if len(nm) else picked_o)

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

# ----- Tab 5: Breadth -----
def breadth_bar(title: str, up: int, down: int,
                up_lbl: str = "Up", dn_lbl: str = "Down") -> None:
    total = max(up + down, 1)
    pct = up / total * 100
    st.markdown(
        f"""<div style="margin:14px 0 4px">
        <div style="display:flex;justify-content:space-between">
          <span style="color:#fff;font-weight:800">{title}</span>
          <span style="color:{MINT if pct >= 50 else '#e05a5a'};
                       font-weight:900">{pct:.0f} %</span>
        </div>
        <div style="background:#243063;border-radius:6px;height:12px;
                    overflow:hidden;margin:6px 0">
          <div style="background:{MINT};width:{pct:.1f}%;height:100%"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:13px">
          <span style="color:{MINT};font-weight:700">{up} {up_lbl}</span>
          <span style="color:#e05a5a;font-weight:700">{down} {dn_lbl}</span>
        </div></div>""",
        unsafe_allow_html=True,
    )


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
            c1, c2 = st.columns(2)
            with c1:
                breadth_bar("New Highs vs New Lows", b["nh"], b["nl"],
                            "Highs", "Lows")
                breadth_bar("Advance vs Decline", b["adv"], b["dec"],
                            "Advance", "Decline")
                if "up_open" in b:
                    breadth_bar("Up from Open vs Down from Open",
                                b["up_open"], b["dn_open"])
            with c2:
                if "up_vol" in b:
                    breadth_bar("Up on Volume vs Down on Volume",
                                b["up_vol"], b["dn_vol"])
                breadth_bar("Up 4% vs Down 4%", b["up4"], b["dn4"])

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
    st.caption("Futures/Makro-Universum (futures.csv).")
    edited_f = st.data_editor(load_csv(FUTURES_FILE), num_rows="dynamic",
                              use_container_width=True, key="ed_fut")
    if st.button("Futures speichern"):
        save_csv(edited_f, FUTURES_FILE)
        st.cache_data.clear()
        st.success("Gespeichert.")
