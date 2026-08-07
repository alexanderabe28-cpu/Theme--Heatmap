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

tab_map, tab_fut, tab_watch, tab_ovsd, tab_universe = st.tabs(
    ["Aktien / ETF", "Futures / Makro", "Watchlist", "OvsD", "Universum"])

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
    col_l, col_r = st.columns([2, 1])
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

            def col_pct(v):
                if pd.isna(v):
                    return ""
                if v > 0.05:
                    return f"background-color: rgba(63,224,160,{min(abs(v)/8,0.85):.2f}); color: #fff"
                if v < -0.05:
                    return f"background-color: rgba(224,90,90,{min(abs(v)/8,0.85):.2f}); color: #fff"
                return f"background-color: {NAVY_CARD}; color: #fff"

            styled = (tbl.style
                      .map(col_pct, subset=["1D", "1W", "2W", "4W"])
                      .format({"Kurs": "{:,.2f}", "1D": "{:+.2f} %", "1W": "{:+.2f} %",
                               "2W": "{:+.2f} %", "4W": "{:+.2f} %"}))
            st.dataframe(styled, use_container_width=True, hide_index=True,
                         height=42 + 35 * len(tbl))
            missing_w = tbl[tbl["1D"].isna()]["Ticker"].tolist()
            if missing_w:
                st.caption(f"Ohne Daten: {', '.join(missing_w)}")
            st.caption(
                f"Sortiert nach 1D · Stand: {closes_w.index[-1]:%Y-%m-%d} · "
                f"Quelle: Yahoo (~15 min)"
            )

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

# ----- Tab 5: Universum -----
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
