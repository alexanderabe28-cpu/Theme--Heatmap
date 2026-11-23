"""Streamlit-Tab "Correction Risk" (Eigenbau nach TSF-Struktur, Spec v1.1).

Einbau im Dashboard:

    from tab_correction_risk import render_correction_risk_tab
    with tab_correction:
        render_correction_risk_tab()

Abhaengigkeiten: streamlit, plotly, pandas, numpy, yfinance, correction_risk.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import correction_risk as cr

# Darstellung 1:1 aus docs/correction_risk/correction_risk.pine (Version 6.0).
# Pine-Transparenz t entspricht hier Deckkraft 1 - t/100.
C_L = {1: "#fab219", 2: "#ec835a", 3: "#d03b3b", 4: "#b04fd0"}   # ELEVATED, HIGH, VERY HIGH, EXTREME
C_CALM = "#3987e5"                                               # Gate an, Level 0
C_OFF = "rgba(138,143,152,0.45)"                                 # ausserhalb des Gates (#8a8f98, t 55)
OP_BAND = {2: 0.26, 3: 0.32, 4: 0.32}                            # Baender: L2 t 74, L3/L4 t 68
OP_WIN_PRICE, OP_WIN_PANE = 0.12, 0.09                           # Risikofenster: t 88 im Kurs, t 91 in der Leiste
CANDLE_UP, CANDLE_DN = "#089981", "#f23645"                      # TradingView-Standardkerzen
MARK_MIN = 2                      # Level-Marker ab diesem Level (Pine-Vorgabe "Marker ab Level" = 2)
MARK_INK = "#1a1a19"
RANGES = {"6 Monate": 126, "1 Jahr": 252, "2 Jahre": 504, "5 Jahre": 1260}
# Zeile "Quote / Basis" der Pine-Tabelle: eingefrorene Quoten 2000–2026 je Level 0..4
# (Rueckgang >= 5 % binnen 45 Sessions) und die Basis aller Gate-Tage. Nur Anzeige.
PINE_QUOTE = {"S&P 500": ([18.6, 24.8, 27.8, 42.2, 38.3], 23.1),
              "NASDAQ": ([29.1, 35.3, 37.9, 39.5, 53.1], 32.5)}
SAMPLE_ROLE = "1999–2007: blinder Test mit Proxys · 2007–2016: Entwicklung · 2017–2026: Holdout, nicht blind"


def _pct(x, digits: int = 1) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x * 100:.{digits}f} %".replace(".", ",")


def _num(x, digits: int = 2) -> str:
    return f"{x:.{digits}f}".replace(".", ",")


def _stretch(fn, *args, **kwargs):
    """Volle Breite in neuen und alten Streamlit-Versionen."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except TypeError:
        return fn(*args, use_container_width=True, **kwargs)


@st.cache_data(ttl=3600, show_spinner="Lade Kurse …")
def _prices() -> pd.DataFrame:
    return cr.load_prices("2005-01-01")


@st.cache_data(ttl=3600, show_spinner=False)
def _model(px: pd.DataFrame) -> pd.DataFrame:
    return cr.add_outcomes(cr.compute_levels(px))


@st.cache_data(ttl=3600, show_spinner=False)
def _ohlc() -> pd.DataFrame:
    """SPY-Kerzen und QQQ-Schluss, bereinigt wie die Modellreihen (Yahoo, auto_adjust).

    Nur fuer Kerzenchart und NASDAQ-Spalte; das Modell rechnet weiter allein mit
    correction_risk.load_prices.
    """
    import yfinance as yf

    raw = yf.download(["SPY", "QQQ"], start="2005-01-01", auto_adjust=True,
                      progress=False, threads=False, group_by="column")
    out = pd.DataFrame({"open": raw["Open"]["SPY"], "high": raw["High"]["SPY"],
                        "low": raw["Low"]["SPY"], "close": raw["Close"]["SPY"],
                        "qqq": raw["Close"]["QQQ"]})
    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out.dropna(subset=["close"])


def _nasdaq(df: pd.DataFrame, qqq: pd.Series) -> pd.DataFrame:
    """NASDAQ-Spalte wie im Pine: dieselben vier Bestaetigungen, Gate auf QQQ
    (hoechstens 3 % unter dem 252-Tage-Schlusshoch). Parameter aus correction_risk.P."""
    q = qqq.reindex(df.index)
    hi = q.rolling(cr.P.gate_lookback).max()
    gate = (q >= (1 - cr.P.gate_pct) * hi).where(hi.notna())
    valid = df["valid"] & gate.notna()
    return pd.DataFrame({"gate": gate, "dist_high": q / hi - 1.0,
                         "level": (df["n_conf"] * gate.astype(float)).where(valid),
                         "valid": valid}, index=df.index)


def _side(level: pd.Series, gate: pd.Series, dist: pd.Series, valid: pd.Series) -> dict:
    """Stand eines Index fuer die Pine-Tabelle: Gate, Abstand, juengster Marker, Fenster."""
    v = valid.fillna(False).astype(bool)
    if not v.any():
        return {"ok": False}
    lvl = level[v]
    marks = cr.level_markers(lvl)
    marks = marks[marks >= MARK_MIN]
    since = cr.sessions_since_warn(lvl).iloc[-1]
    return {"ok": True, "gate": bool(gate[v].iloc[-1]), "dist": float(dist[v].iloc[-1]),
            "mark": (marks.index[-1], int(marks.iloc[-1])) if len(marks) else None,
            "win": int(since) if pd.notna(since) and since <= cr.P.horizon else None}


def _pine_pct(x: float) -> str:
    """Wie pct() im Pine: Minuszeichen, eine Nachkommastelle, Komma."""
    if x is None or np.isnan(x):
        return "–"
    return ("−" if x < -0.0005 else "") + f"{abs(x) * 100:.1f} %".replace(".", ",")


def _rgba(hex_col: str, alpha: float) -> str:
    h = hex_col.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


def _pine_table(s: dict, sides: dict, datum: pd.Timestamp) -> str:
    """Tabelle "Correction Risk" wie oben rechts im Pine-Indikator, als HTML."""
    n = s["n_conf"]
    fg, dim, line = "#e8ecf2", "#9fb0e8", "rgba(232,236,242,0.15)"
    cell = f"padding:4px 8px;border:1px solid {line};font-size:12.5px;white-space:nowrap"

    def state(sd):
        if not sd["ok"]:
            return "keine Daten", _rgba("#8a8f98", 0.2)
        if not sd["gate"]:
            return "kein Level", _rgba("#8a8f98", 0.2)
        return f"{n} {cr.LEVEL_NAMES[n]}", _rgba(C_CALM, 0.25) if n == 0 else _rgba(C_L[n], 0.6)

    def rate(name, sd):
        if not sd["ok"] or not sd["gate"]:
            return "–"
        q, b = PINE_QUOTE[name]
        return f"{q[min(n, 4)]:.1f} % / {b:.1f} %".replace(".", ",")

    def mark(sd):
        m = sd.get("mark")
        return "–" if not m else f"{m[1]} am {m[0]:%d.%m.%y}"

    def win(sd):
        return ("zu", "") if sd.get("win") is None else (f"Tag {sd['win']} von {cr.P.horizon}",
                                                       f"background:{_rgba(C_L[3], 0.3)};")

    names = list(sides)
    letters = " ".join(c if s["komponenten"][c] else "·" for c in cr.COMPONENTS)
    rows = [("Level", [state(sides[k]) for k in names],
             "Level = Zahl der Bestätigungen an Gate-Tagen: 1 ELEVATED, 2 HIGH, 3 VERY HIGH, 4 EXTREME. Warnzustand ab 3."),
            ("unter Hoch", [(_pine_pct(sides[k].get("dist", np.nan)), "") for k in names],
             "Abstand zum 252-Tage-Schlusshoch. Gate an bis −3 %."),
            ("Bestätigt", None, "C Credit (HYG/IEF), B Breadth (RSP), R Rotation (XLY/XLP), V Volatility (VIX)"),
            ("Marker", [(mark(sides[k]), "") for k in names],
             "Jüngstes Erstsignal ab Level 2: Level und Datum."),
            ("Fenster", [win(sides[k]) for k in names],
             "Risikofenster: 45 Sessions nach dem letzten Tag im Warnzustand. Kein Ausstiegssignal."),
            ("Quote / Basis", [(rate(k, sides[k]), "") for k in names],
             "2000–2026: Anteil der Tage mit diesem Level, denen binnen 45 Sessions ein Schluss "
             "mindestens 5 % tiefer folgte, und die Basis aller Gate-Tage. Nicht belegt.")]
    html = [f"<table style='border-collapse:collapse;color:{fg};margin-left:auto;"
            f"background:rgba(16,24,47,0.9)'>",
            f"<tr><td style='{cell}'>Correction Risk</td>"
            + "".join(f"<td style='{cell};text-align:center'>{k}</td>" for k in names) + "</tr>"]
    for label, vals, tip in rows:
        html.append(f"<tr><td style='{cell};color:{dim}' title='{tip}'>{label}</td>")
        if vals is None:
            html.append(f"<td colspan='{len(names)}' style='{cell};text-align:center'>"
                        f"{letters}&nbsp;&nbsp;&nbsp;{n} von 4</td>")
        else:
            for text, bg in vals:
                style = f"background:{bg};" if bg and not bg.startswith("background") else bg
                html.append(f"<td style='{cell};text-align:center;{style}'>{text}</td>")
        html.append("</tr>")
    html.append(f"<tr><td colspan='{len(names) + 1}' style='{cell};color:{dim}'>"
                f"{datum:%d.%m.%Y} · Schattenmodus, nicht belegt</td></tr></table>")
    return "".join(html)


@st.cache_data(ttl=86400, show_spinner="Rechne Erstsignal-Test …")
def _stats(df: pd.DataFrame) -> dict:
    return {
        "gesamt": cr.evaluate(df),
        "h1": cr.evaluate(df, end="2016-12-31", with_placebo=False),
        "h2": cr.evaluate(df, start="2017-01-01", with_placebo=False),
    }


def _state_name(level: int, gate: bool) -> str:
    if not gate:
        return "kein Level"
    return f"{level} {cr.LEVEL_NAMES[int(level)]}"


def _spans(level: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    """Zusammenhaengende Abschnitte mit Level 2, 3 oder 4."""
    out, start, cur = [], None, 0
    idx = level.index
    vals = level.fillna(0).astype(int).to_numpy()
    for i, v in enumerate(vals):
        v = v if v in (2, 3, 4) else (4 if v > 4 else 0)
        if v != cur:
            if cur:
                out.append((start, idx[i], cur))
            start, cur = idx[i], v
    if cur:
        out.append((start, idx[-1] + pd.Timedelta(days=1), cur))
    return out


def _state_table() -> pd.DataFrame:
    """Zustandsquoten je Level und Stichprobe aus dem eingefrorenen Volltest."""
    bt = cr.BACKTEST
    cols = [(s["label"], s) for s in bt["samples"]] + [("Gesamt", bt["gesamt"])]
    rows = []
    for k in range(5):
        row = {"Zustand": f"Level {k}"}
        for label, s in cols:
            row[label] = f"{_pct(s['quote'][k])} ({s['tage'][k]})"
        rows.append(row)
    row = {"Zustand": "Warnzustand (≥ 3)"}
    for label, s in cols:
        row[label] = f"{_pct(s['ab3']['quote'])} ({s['ab3']['tage']})"
    rows.append(row)
    row = {"Zustand": "Alle Gate-Tage"}
    for label, s in cols:
        row[label] = f"{_pct(s['basis'])} ({s['gate_tage']})"
    rows.append(row)
    return pd.DataFrame(rows)


def _component_table() -> pd.DataFrame:
    bt = cr.BACKTEST
    names = dict(cr.COMPONENTS, S="Small Caps (IWM)", F="Financials (XLF/SPY)", D="Sektorbreite (5 von 9)")
    rows = []
    for c, per in bt["komponenten"].items():
        row = {"Komponente": names[c], "Status": "im Modell" if c in cr.COMPONENTS else "getestet, verworfen"}
        for s in bt["samples"]:
            row[f"Lift {s['label']}"] = _num(per[s["key"]][0])
        rows.append(row)
    return pd.DataFrame(rows)


def _first_signal_table(stats: dict) -> pd.DataFrame:
    g, h1, h2 = stats["gesamt"], stats["h1"], stats["h2"]
    rows = []
    for a, b, c in zip(g["levels"], h1["levels"], h2["levels"]):
        rows.append({
            "Schwelle": f"Level ≥ {a['k']}",
            "Episoden": a["episoden"],
            "Treffer": a["treffer"],
            "Quote": _pct(a["quote"]),
            "Baseline": _pct(a["baseline"]),
            "p (Placebo)": "–" if np.isnan(a["p_placebo"]) else _num(a["p_placebo"], 3),
            "bis 2016": f"{b['treffer']}/{b['episoden']}",
            "ab 2017": f"{c['treffer']}/{c['episoden']}",
        })
    return pd.DataFrame(rows)


def _chart(df: pd.DataFrame, ohlc: pd.DataFrame | None, n: int) -> go.Figure:
    """Kurschart und Leiste wie der Pine-Indikator auf einem SPY-Tageschart.

    Oben Kerzen mit Risikofenster, Baendern (Level 2-4 an Gate-Tagen) und Level-Markern
    (Dreieck ueber dem Balken, darunter "LEVEL n · Bestaetigungen"). Unten die Saeulen
    der Bestaetigungen, grau ausserhalb des Gates, mit Warnschwelle 3 und Gate-Leiste.
    """
    valid = df[df["valid"]]
    d = valid.tail(n)
    k = ohlc.reindex(d.index) if ohlc is not None else None
    candles = k is not None and k[["open", "high", "low", "close"]].notna().all(axis=1).mean() > 0.95
    hi_s = k["high"].fillna(d["spy"]) if candles else d["spy"]
    lo_s = k["low"].fillna(d["spy"]) if candles else d["spy"]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.74, 0.26],
                        vertical_spacing=0.03)
    half = pd.Timedelta(hours=12)              # Baender von Balkenmitte zu Balkenmitte

    def band(start, end, color, opacity, yref):
        return dict(type="rect", xref="x", yref=yref, x0=start - half, x1=end - half, y0=0, y1=1,
                    fillcolor=color, opacity=opacity, line_width=0, layer="below")

    # Risikofenster (auf der ganzen Historie gerechnet), darueber die Baender des Tages
    since = cr.sessions_since_warn(valid["level"]).reindex(d.index)
    shapes = []
    for start, end, _ in _spans((since <= cr.P.horizon).astype(int) * 3):
        shapes += [band(start, end, C_L[3], OP_WIN_PRICE, "y domain"),
                   band(start, end, C_L[3], OP_WIN_PANE, "y2 domain")]
    for start, end, lvl in _spans(d["level"]):
        shapes.append(band(start, end, C_L[lvl], OP_BAND[lvl], "y domain"))
    fig.update_layout(shapes=shapes)

    comps = d[list(cr.COMPONENTS)].apply(
        lambda r: "".join(c for c in cr.COMPONENTS if r[c] == True) or "–", axis=1)  # noqa: E712
    info = [f"Level {int(l)} {cr.LEVEL_NAMES[int(l)] if g else '(Gate aus)'} · {c} · "
            f"{_pine_pct(x)} zum Hoch" for l, g, c, x in
            zip(d["level"], d["gate"] == True, comps, d["dist_high"])]  # noqa: E712
    if candles:
        fig.add_trace(go.Candlestick(
            x=d.index, open=k["open"], high=k["high"], low=k["low"], close=k["close"], name="SPY",
            increasing=dict(line=dict(color=CANDLE_UP), fillcolor=CANDLE_UP),
            decreasing=dict(line=dict(color=CANDLE_DN), fillcolor=CANDLE_DN),
            text=info, hoverinfo="x+y+text", showlegend=False), row=1, col=1)
    else:                                      # ohne OHLC (Yahoo nicht erreichbar): Schlusskurs als Linie
        fig.add_trace(go.Scatter(x=d.index, y=d["spy"], mode="lines", name="SPY", text=info,
                                 line=dict(color=C_CALM, width=1.6), showlegend=False), row=1, col=1)

    # Level-Marker: erster Tag, an dem das Level hoeher ist als an den 20 Sessions davor.
    # Auf der ganzen Historie gerechnet, damit die 20 Sessions vor dem Fenster zaehlen.
    marks = cr.level_markers(valid["level"])
    marks = marks[(marks >= MARK_MIN) & (marks.index >= d.index[0])]
    span = max(float(hi_s.max() - lo_s.min()), 1e-9)
    if len(marks):
        tips = [f"{t:%d.%m.%Y} · Level {m} {cr.LEVEL_NAMES[m]} · {comps.at[t]} · "
                f"{_pine_pct(d.at[t, 'dist_high'])} zum Hoch" for t, m in marks.items()]
        fig.add_trace(go.Scatter(
            x=marks.index, y=[hi_s.at[t] + 0.025 * span for t in marks.index], mode="markers",
            marker=dict(symbol="triangle-down", size=13, color=[C_L[m] for m in marks]),
            text=tips, hoverinfo="text", name="Level-Marker", showlegend=False), row=1, col=1)
        # Liegen Marker nur wenige Sessions auseinander, Beschriftungen untereinander stapeln
        pos, stack, prev = {t: d.index.get_loc(t) for t in marks.index}, 0, None
        gap = max(3, n // 40)
        for t, m in marks.items():
            if prev is not None and pos[t] - prev <= gap:
                stack, base = stack + 1, min(base, lo_s.at[t])
            else:
                stack, base = 0, lo_s.at[t]
            prev = pos[t]
            fig.add_annotation(
                x=t, y=base, xref="x", yref="y", yanchor="top", yshift=-8 - 20 * stack,
                showarrow=False,
                text=f"LEVEL {m} · {comps.at[t]}", bgcolor=C_L[m], borderpad=3,
                font=dict(color="#ffffff" if m >= 3 else MARK_INK, size=10),
                hovertext=f"{t:%d.%m.%Y} · Level {m} {cr.LEVEL_NAMES[m]} · {comps.at[t]} · "
                          f"{_pine_pct(d.at[t, 'dist_high'])} zum Hoch")

    # Leiste: Saeulen = Zahl der Bestaetigungen; Farbe nach Level, grau ausserhalb des Gates
    nconf = d["n_conf"].astype(int)
    gate_on = (d["gate"] == True)  # noqa: E712
    cols = [C_L.get(v, C_CALM) if g else C_OFF for v, g in zip(nconf, gate_on)]
    fig.add_trace(go.Bar(x=d.index, y=nconf, marker_color=cols, marker_line_width=0,
                         name="Bestätigungen", showlegend=False,
                         hovertemplate="Bestätigungen %{y}<extra></extra>"), row=2, col=1)
    fig.add_trace(go.Scatter(x=d.index[gate_on], y=[-0.4] * int(gate_on.sum()), mode="markers",
                             marker=dict(symbol="square", size=4, color=_rgba(C_CALM, 0.8)),
                             name="Gate an", hoverinfo="skip", showlegend=False), row=2, col=1)
    fig.add_hline(y=cr.WARN_LEVEL, line=dict(color=_rgba(C_L[3], 0.7), dash="dash", width=1), row=2, col=1)
    fig.add_hline(y=4, line=dict(color=_rgba("#8a8f98", 0.3), dash="dot", width=1), row=2, col=1)

    # Handelstage lueckenlos wie in TradingView: Wochenenden und Feiertage ausblenden
    holidays = pd.bdate_range(d.index[0], d.index[-1]).difference(d.index)
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(values=list(holidays))],
                     showgrid=False, hoverformat="%d.%m.%Y", tickformat="%m.%y")
    fig.update_layout(
        height=640, margin=dict(l=8, r=8, t=8, b=8), hovermode="x unified", bargap=0.15,
        xaxis_rangeslider_visible=False, showlegend=False,
        yaxis=dict(title=None, tickformat=".0f", gridcolor="rgba(128,128,128,0.18)",
                   range=[float(lo_s.min()) - 0.10 * span, float(hi_s.max()) + 0.07 * span]),
        yaxis2=dict(title=None, range=[-0.7, 4.4], tickvals=[0, 1, 2, 3, 4],
                    gridcolor="rgba(128,128,128,0.12)"),
    )
    return fig


def render_correction_risk_tab(px: pd.DataFrame | None = None) -> None:
    """Zeichnet den Tab. `px` nur fuer Tests uebergeben, sonst werden Kurse geladen."""
    bt = cr.BACKTEST
    by_key = {s["key"]: s for s in bt["samples"]}
    st.subheader("Correction Risk")
    st.caption(f"Eigenbau nach TSF-Struktur · Spec v{cr.SPEC_VERSION} · Schattenmodus · SPY täglich · Daten: Yahoo Finance")
    try:
        px = _prices() if px is None else px
    except Exception as exc:                      # Yahoo nicht erreichbar o. ä.
        st.error(f"Kurse konnten nicht geladen werden: {exc}")
        return
    df = _model(px)
    s = cr.current_state(df)
    try:
        ohlc = _ohlc()
    except Exception:                             # Kerzen und NASDAQ sind Zusatz, das Modell laeuft ohne
        ohlc = None

    # Tabelle wie im Pine-Indikator (oben rechts): S&P 500 und NASDAQ nebeneinander
    sides = {"S&P 500": _side(df["level"], df["gate"], df["dist_high"], df["valid"])}
    if ohlc is not None and ohlc["qqq"].notna().any():
        nq = _nasdaq(df, ohlc["qqq"])
        sides["NASDAQ"] = _side(nq["level"], nq["gate"], nq["dist_high"], nq["valid"])
    else:
        sides["NASDAQ"] = {"ok": False}

    left, right = st.columns([3, 2])
    with left:
        st.caption(f"Stand: Schluss {s['datum']:%d.%m.%Y}")
        if not s["gate"]:
            st.info(f"Außerhalb Gate: SPY liegt {_pct(abs(s['dist_high']))} unter dem 252-Tage-Hoch. "
                    "Das Modell bewertet nur Tops nahe Hoch und gibt hier kein Level aus.")
        st.warning(
            "Schattenmodus, nicht belegt. Im Warnzustand folgte "
            f"{by_key['E']['label']} an {_pct(by_key['E']['ab3']['quote'], 0)} und {by_key['H1']['label']} an "
            f"{_pct(by_key['H1']['ab3']['quote'], 0)} der Tage ein Rückgang ≥ 5 %, im blinden Test {by_key['H2']['label']} "
            f"nur an {_pct(by_key['H2']['ab3']['quote'], 0)} bei {_pct(by_key['H2']['basis'], 0)} Basisrate. "
            "Anzeige als Marktkontext, keine Handlungsautorität.")
    with right:
        st.markdown(_pine_table(s, sides, s["datum"]), unsafe_allow_html=True)

    rng = st.radio("Zeitraum", list(RANGES), index=1, horizontal=True, key="cr_range")
    _stretch(st.plotly_chart, _chart(df, ohlc, RANGES[rng]), key="cr_chart")
    st.caption(
        "Darstellung wie der TradingView-Indikator auf SPY, Tageschart. Säulen unten: Zahl der "
        "Bestätigungen, grau außerhalb des Gates, blaue Leiste = Gate an, gestrichelt die "
        f"Warnschwelle {cr.WARN_LEVEL}. Bänder im Kurs: orange 2 HIGH, rot 3 VERY HIGH, violett "
        f"4 EXTREME, nur an Gate-Tagen. Blasses Rot: Risikofenster, {cr.P.horizon} Sessions nach dem "
        "letzten Tag im Warnzustand, Messfenster des Backtests und kein Ausstiegssignal. "
        f"Marker ab Level {MARK_MIN}: erster Tag, an dem das Level höher ist als an den "
        f"{cr.P.episode_gap} Sessions davor, als Einzelsignal nicht belegt. Die Kerzen sind wie das "
        "Modell dividendenbereinigt und liegen deshalb leicht unter den TradingView-Kursen.")

    st.markdown("**Volltest: Level als Zustand** · Anteil der Tage, denen binnen 45 Sessions ein Schluss "
                "≥ 5 % unter dem Tagesschluss folgte (in Klammern: Zahl der Tage)")
    _stretch(st.dataframe, _state_table(), hide_index=True)
    st.caption(SAMPLE_ROLE)

    track = cr.forward_track(df)
    fs = cr.forward_summary(track)
    st.markdown(f"**Live-Test (Tage nach dem {pd.Timestamp(cr.FREEZE_DATE):%d.%m.%Y})** · im Warnzustand: {fs['tage']} · "
                f"ausgewertet: {fs['bekannt']} · Treffer: {fs['treffer']} · offen: {fs['offen']}")
    if len(track):
        show = track.copy()
        show.index = show.index.strftime("%d.%m.%Y")
        show["y45"] = show["y45"].map({1.0: "Treffer", 0.0: "kein Treffer"}).fillna("offen")
        show = show.rename(columns={"level": "Level", "komponenten": "Komponenten", "spy": "SPY", "y45": "Ausgang"})
        _stretch(st.dataframe, show.round({"SPY": 2}))

    with st.expander("Erstsignal-Test (erster Tag einer Episode)"):
        stats = _stats(df)
        g = stats["gesamt"]
        st.markdown(f"Backtest {g['von'][:4]}–{g['bis'][:4]}, Baseline an Gate-Tagen {_pct(g['baseline_y45'])}. "
                    "Als Erstsignal hat kein Level einen belegten Vorsprung.")
        _stretch(st.dataframe, _first_signal_table(stats), hide_index=True)

    with st.expander("Komponenten je Ära"):
        st.markdown("Lift = Quote an Tagen mit aktiver Komponente geteilt durch die Basisrate der Ära. "
                    "Die Rangfolge kippt zwischen den Ären, deshalb gibt es keine Gewichte.")
        _stretch(st.dataframe, _component_table(), hide_index=True)

    with st.expander("Regeln und Grenzen"):
        st.markdown(
            "- **Gate:** SPY-Schluss höchstens 3 % unter dem 252-Tage-Schlusshoch.\n"
            "- **Komponenten:** Reihe auf der Risk-off-Seite ihres 50-Tage-SMA und 20-Tage-Veränderung in Risk-off-Richtung. "
            "C = HYG/IEF, B = RSP, R = XLY/XLP, V = VIX.\n"
            "- **Level:** Zahl der wahren Komponenten an Gate-Tagen (0–4). Warnzustand ab 3.\n"
            "- **Lesart:** Zustand, nicht Erstsignal. Level 4 war nicht gefährlicher als Level 3.\n"
            "- **Tests:** Entwicklung nur auf 2007–2016, danach je ein Lauf auf 2017–2026 und 1999–2007. "
            f"Brier-Test gegen die Basisrate nicht bestanden (p = {_num(by_key['H1']['p_T1'])} und {_num(by_key['H2']['p_T1'])}), "
            "blinder Test 1999–2007 nicht bestanden.\n"
            f"- **Kosten:** Mittlere 45-Sessions-Rendite im Warnzustand 2017–2026: {_pct(by_key['H1']['fwd45_ab3'])}, "
            f"an allen Gate-Tagen {_pct(by_key['H1']['fwd45_gate'])} (nur abgeschlossene Fenster). "
            "Aussteigen hat sich im Schnitt nicht ausgezahlt.\n"
            "- **Grenzen:** Rund drei Korrekturen pro Jahr reichen nicht, um ein Modell dieser Art statistisch zu belegen. "
            "Die TSF-Inputs sind unbekannt, das ist kein Nachbau der TSF-Zahlen."
        )
