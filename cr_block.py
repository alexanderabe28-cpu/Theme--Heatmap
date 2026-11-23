"""Correction Risk v1.1: R-/W-Block fuer die Project-Instructions "Daily & Weekly".

Aufruf im Repo-Ordner:  python cr_block.py [--prices pfad.csv] [--out out/cr_latest.md]
Exit 0 = ok, 1 = Daten aelter als 4 Kalendertage (Block mit Hinweis), 2 = keine Daten.
Rechnet nur mit correction_risk.py, aendert keine Parameter.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

import correction_risk as cr

H1 = next(s for s in cr.BACKTEST["samples"] if s["key"] == "H1")


def _d(ts) -> str:
    return pd.Timestamp(ts).strftime("%d.%m.%Y")


def _pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f} %".replace(".", ",")


def build(px: pd.DataFrame, today: pd.Timestamp | None = None) -> tuple[str, int]:
    df = cr.add_outcomes(cr.compute_levels(px))
    d = df[df["valid"]]
    st = cr.current_state(df)
    lvl, gate = st["level"], st["gate"]
    since = cr.sessions_since_warn(d["level"])
    n_since = since.iloc[-1]
    warn_days = d.index[d["level"] >= cr.WARN_LEVEL]
    marks = cr.level_markers(d["level"])
    marks = marks[marks >= 2]
    letters = "".join(c for c, on in st["komponenten"].items() if on) or "–"
    fs = cr.forward_summary(cr.forward_track(df))

    today = pd.Timestamp(today or pd.Timestamp.today().normalize())
    age = (today - st["datum"]).days
    code = 1 if age > 4 else 0

    if gate and lvl > 0:
        zustand = f"Level {lvl} {cr.LEVEL_NAMES[lvl]} · {letters}"
        quote = f"Quote Level {lvl} im Holdout 2017–2026: {_pct(H1['quote'][lvl])} ({H1['tage'][lvl]} Tage, Basis {_pct(H1['basis'])})"
    elif gate:
        zustand, quote = "Level 0 (Gate an, keine Bestätigung)", ""
    else:
        zustand = "kein Level (Gate aus)"
        quote = ""
    if pd.notna(n_since) and n_since <= cr.P.horizon:
        fenster = f"Tag {int(n_since)} von {cr.P.horizon}, letzter Warntag {_d(warn_days[-1])} (Level {int(d.loc[warn_days[-1], 'level'])})"
    else:
        fenster = "geschlossen" + (f", letzter Warntag {_d(warn_days[-1])}" if len(warn_days) else "")
    last_marks = ", ".join(f"{_d(t)} L{v}" for t, v in marks.tail(3).items()) or "–"

    lines = [
        f"### Correction Risk (CR) · S&P 500 · Stand {_d(st['datum'])}",
        "",
        "Spec v1.1, Schattenmodus, nicht belegt. Keine Handlung daraus.",
        "",
        f"- Zustand: {zustand}",
        f"- Gate (SPY ≥ 97 % des 252-Tage-Hochs): {'an' if gate else 'aus'}, Abstand {_pct(st['dist_high'])}",
        f"- Bestätigungen: {st['n_conf']} von 4 ({letters})",
        f"- Risikofenster: {fenster}",
        f"- Letzte Marker (ab Level 2): {last_marks}",
        f"- Live-Test seit {_d(cr.FREEZE_DATE)}: {fs['tage']} Warntage, {fs['bekannt']} ausgewertet, {fs['treffer']} Treffer, {fs['offen']} offen",
    ]
    if quote:
        lines.append(f"- {quote}")
    if code:
        lines.insert(2, f"Datenstand: letzte Kerze {_d(st['datum'])}, {age} Kalendertage alt.")
        lines.insert(3, "")

    # W-Block: Marker und Warntage der letzten 5 Sessions
    week = d.index[-5:]
    wk_marks = marks[marks.index.isin(week)]
    wk_warn = [t for t in warn_days if t in week]
    lines += [
        "",
        "### Correction Risk · W-Block",
        "",
        f"- Woche {_d(week[0])}–{_d(week[-1])}: Level je Tag "
        + " ".join(f"{int(v) if g else '–'}" for v, g in zip(d.loc[week, 'level'], d.loc[week, 'gate'])),
        f"- Neue Marker: {', '.join(f'{_d(t)} L{v}' for t, v in wk_marks.items()) or 'keine'}",
        f"- Warntage: {', '.join(_d(t) for t in wk_warn) or 'keine'}",
    ]
    return "\n".join(lines) + "\n", code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", help="CSV-Cache statt Yahoo")
    ap.add_argument("--out", default="out/cr_latest.md")
    a = ap.parse_args()
    try:
        px = (pd.read_csv(a.prices, index_col=0, parse_dates=True) if a.prices
              else cr.load_prices("2005-01-01"))
        if px.empty:
            raise ValueError("keine Kursdaten")
        text, code = build(px)
    except Exception as e:  # noqa: BLE001
        print(f"CR n/a: {type(e).__name__}: {e}")
        return 2
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
