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

import correction_risk as cr

# Statusfarben (Warnung / ernst), immer mit Textlabel in der Legende
BAND = {2: ("#ec835a", "2 HIGH"), 3: ("#d03b3b", "3 VERY HIGH"), 4: ("#b04fd0", "4 EXTREME")}
MARK_COL = {1: "#fab219", 2: "#ec835a", 3: "#d03b3b", 4: "#b04fd0"}
LINE = "#3987e5"
MARK_MIN = 2                      # Level-Marker ab diesem Level
MARK_INK = "#1a1a19"
RANGES = {"6 Monate": 126, "1 Jahr": 252, "2 Jahre": 504, "5 Jahre": 1260}
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


def _chart(df: pd.DataFrame, n: int) -> go.Figure:
    d = df[df["valid"]].tail(n)
    fig = go.Figure()
    shapes = []
    # Risikofenster: bis P.horizon Sessions nach dem letzten Tag im Warnzustand, auf der ganzen Historie gerechnet
    since = cr.sessions_since_warn(df[df["valid"]]["level"]).reindex(d.index)
    for start, end, _ in _spans((since <= cr.P.horizon).astype(int) * 3):
        shapes.append(dict(type="rect", xref="x", yref="paper", x0=start, x1=end, y0=0, y1=1,
                           fillcolor=BAND[3][0], opacity=0.13, line_width=0, layer="below"))
    for start, end, lvl in _spans(d["level"]):
        shapes.append(dict(type="rect", xref="x", yref="paper", x0=start, x1=end, y0=0, y1=1,
                           fillcolor=BAND[lvl][0], opacity=0.30, line_width=0, layer="below"))
    fig.update_layout(shapes=shapes)
    comps = d[list(cr.COMPONENTS)].apply(lambda r: "".join(c for c in cr.COMPONENTS if r[c] == True) or "–", axis=1)  # noqa: E712
    custom = np.stack([d["level"].astype(int), comps, d["dist_high"] * 100,
                       np.where(d["gate"] == True, "an", "aus")], axis=-1)  # noqa: E712
    fig.add_trace(go.Scatter(
        x=d.index, y=d["spy"], mode="lines", name="SPY",
        line=dict(color=LINE, width=2), customdata=custom, showlegend=False,
        hovertemplate="SPY %{y:.2f}<br>Level %{customdata[0]} [%{customdata[1]}]"
                      "<br>Gate %{customdata[3]}, %{customdata[2]:.1f} % zum Hoch<extra></extra>"))
    for lvl, (col, label) in BAND.items():   # Legendeneintraege fuer die Baender
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=label,
                                 marker=dict(symbol="square", size=11, color=col, opacity=0.6)))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=f"Risikofenster ({cr.P.horizon} Sessions)",
                             marker=dict(symbol="square", size=11, color=BAND[3][0], opacity=0.25)))
    # Level-Marker: erster Tag, an dem das Level hoeher ist als an den 20 Sessions davor.
    # Auf der ganzen Historie gerechnet, damit die 20 Sessions vor dem Fenster zaehlen.
    marks = cr.level_markers(df[df["valid"]]["level"])
    marks = marks[(marks >= MARK_MIN) & (marks.index >= d.index[0])]
    pos = {t: i for i, t in enumerate(d.index)}
    prev, lift = -99, 0
    for t, k in marks.items():
        lift = lift + 26 if pos[t] - prev < 8 else 0          # nahe Marker stapeln statt ueberdecken
        prev = pos[t]
        fig.add_annotation(
            x=t, y=d.at[t, "spy"], text=f"<b>{k}</b>", showarrow=True, arrowhead=0, arrowwidth=1.4,
            arrowcolor=MARK_COL[k], ax=0, ay=-(26 + lift), bgcolor=MARK_COL[k], borderpad=3,
            font=dict(color="#ffffff" if k >= 3 else MARK_INK, size=12),
            hovertext=f"{t:%d.%m.%Y} · Level {k} {cr.LEVEL_NAMES[k]} [{comps.at[t]}] · {_pct(d.at[t, 'dist_high'])} zum Hoch")
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name="Zahl im Kästchen: Level-Marker",
                             marker=dict(symbol="square", size=12, color=BAND[3][0], line=dict(width=1.5, color=MARK_INK))))
    lo, hi = float(d["spy"].min()), float(d["spy"].max())
    span = max(hi - lo, 1e-9)
    fig.update_layout(
        height=420, margin=dict(l=8, r=8, t=8, b=8), hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
        xaxis=dict(showgrid=False, hoverformat="%d.%m.%Y", tickformat="%m.%y"),
        yaxis=dict(title=None, tickformat=".0f", gridcolor="rgba(128,128,128,0.18)",
                   range=[lo - 0.04 * span, hi + 0.16 * span]),   # Luft nach oben fuer die Marker
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Zustand", _state_name(s["level"], s["gate"]))
    c2.metric("Bestätigungen", f"{s['n_conf']} von 4")
    c3.metric("Gate (≤ 3 % unter Hoch)", "an" if s["gate"] else "aus")
    c4.metric("Abstand 252-Tage-Hoch", _pct(s["dist_high"]))
    since_now = cr.sessions_since_warn(df[df["valid"]]["level"]).iloc[-1]
    fenster = f"Tag {int(since_now)} von {cr.P.horizon}" if since_now <= cr.P.horizon else "zu"
    st.caption(f"Stand: Schluss {s['datum']:%d.%m.%Y} · Risikofenster: {fenster}")

    if not s["gate"]:
        st.info(f"Außerhalb Gate: SPY liegt {_pct(abs(s['dist_high']))} unter dem 252-Tage-Hoch. "
                "Das Modell bewertet nur Tops nahe Hoch und gibt hier kein Level aus.")
    st.warning(
        "Schattenmodus, nicht belegt. Im Warnzustand folgte "
        f"{by_key['E']['label']} an {_pct(by_key['E']['ab3']['quote'], 0)} und {by_key['H1']['label']} an "
        f"{_pct(by_key['H1']['ab3']['quote'], 0)} der Tage ein Rückgang ≥ 5 %, im blinden Test {by_key['H2']['label']} "
        f"nur an {_pct(by_key['H2']['ab3']['quote'], 0)} bei {_pct(by_key['H2']['basis'], 0)} Basisrate. "
        "Anzeige als Marktkontext, keine Handlungsautorität.")

    cols = st.columns(4)
    for col, (key, name) in zip(cols, cr.COMPONENTS.items()):
        col.metric(name, "Risk-off" if s["komponenten"][key] else "neutral")

    rng = st.radio("Zeitraum", list(RANGES), index=1, horizontal=True, key="cr_range")
    _stretch(st.plotly_chart, _chart(df, RANGES[rng]), key="cr_chart")
    st.caption(f"Level-Marker ab Level {MARK_MIN}: erster Tag, an dem das Level höher ist als an den "
               f"{cr.P.episode_gap} Sessions davor. Als Einzelsignal nicht belegt, siehe Erstsignal-Test. "
               f"Blasses Band: Risikofenster, {cr.P.horizon} Sessions nach dem letzten Tag im Warnzustand. "
               "Es ist das Messfenster des Backtests und kein Ausstiegssignal.")

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
