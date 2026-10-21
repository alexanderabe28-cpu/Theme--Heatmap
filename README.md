# Streamlit Community Cloud – Deployment in 4 Schritten

Ergebnis: Die Heatmap-App laeuft dauerhaft unter einer eigenen URL
(https://DEINNAME-heatmap.streamlit.app), auch am Handy. Kostenlos.

## 1. GitHub-Repository anlegen
- https://github.com -> einloggen (oder kostenloses Konto erstellen)
- Oben rechts "+" -> "New repository"
- Name z.B. `theme-heatmap`, Sichtbarkeit **Public**, "Create repository"

## 2. Dateien hochladen
- Im neuen Repo: "uploading an existing file" anklicken
- Diese Dateien aus dem ZIP per Drag & Drop hochladen:
  - heatmap_app.py
  - tickers.csv
  - futures.csv
  - watchlist.csv
  - requirements.txt
  - .streamlit/config.toml  (Ordnerstruktur bleibt im ZIP erhalten;
    falls GitHub den Ordner nicht uebernimmt: "Add file" -> "Create new file",
    als Namen `.streamlit/config.toml` eingeben und Inhalt einfuegen)
- "Commit changes"

## 3. Bei Streamlit Cloud deployen
- https://share.streamlit.io -> "Sign in with GitHub"
- "New app" (bzw. "Create app")
- Repository: `DEINNAME/theme-heatmap` · Branch: `main`
  · Main file path: `heatmap_app.py`
- "Deploy" -> erste Installation dauert 2-3 Minuten

## 4. Nutzen
- Die URL oben im Browser ist deine App – funktioniert auch am Handy
  (Lesezeichen/Homescreen empfohlen)

## Wichtige Hinweise fuer den Cloud-Betrieb
- **Universum aendern:** Aenderungen ueber den Universum-Tab gelten nur bis
  zum naechsten Neustart der Cloud-App (Dateisystem ist fluechtig).
  Dauerhafte Aenderungen: die CSV-Dateien direkt im GitHub-Repo editieren
  (Datei anklicken -> Stift-Symbol -> Commit). Die App uebernimmt das
  automatisch nach ca. 1 Minute.
- **IBKR-Umschalter:** funktioniert nur lokal (TWS/Gateway laeuft auf deinem
  Rechner, nicht in der Cloud). In der Cloud einfach auf Yahoo lassen.
- **Schlafmodus:** Nach ~7 Tagen ohne Nutzung legt Streamlit die App schlafen;
  erster Aufruf danach dauert ~1 Minute (einmal "Wake up" klicken).

# Breadth-Scanner (taegliche Datenerfassung, kostenlos)

Die Breadth- und Scanner-Tabs rechnen nicht live, sondern lesen fertige
Dateien aus `data/`. Diese schreibt ein GitHub-Actions-Lauf jeden Handelstag
um 22:30 UTC (nach US-Schluss) ins Repo – auch wenn niemand die App oeffnet.

```
GitHub Actions (.github/workflows/daily-breadth.yml)
  -> scanner/run_daily.py: Universen laden, Yahoo-Tagesdaten, Kennzahlen
  -> data/*.csv committen
Streamlit-App liest data/ (schnell, keine Yahoo-Last)
```

**Universen** (`data/universe/master.csv`, woechentlich erneuert):
S&P 500 (Wikipedia), Nasdaq Composite (Nasdaq-Screener, ohne Warrants/Units/
SPACs), Russell 2000 (iShares IWM; falls geblockt: Proxy = US-Aktien nach
Market Cap, Rang 1001-3000), Gesamt, und die **Scanner-Liste**.

**Scanner-Kriterien** stehen in `scanner_config.json` (null = aus). Im
Scanner-Tab lassen sie sich live filtern; "Filter als Scanner-Liste speichern"
schreibt die Datei lokal – in der Cloud den angezeigten JSON-Block ins Repo
kopieren.

**Erster Start / Historie neu aufbauen:** GitHub -> Actions -> Daily Breadth
-> Run workflow -> `backfill_years = 2`.

**Lokal ausfuehren:**

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-pipeline.txt
.venv\Scripts\python -m scanner.run_daily              # Tageslauf
.venv\Scripts\python -m scanner.run_daily --limit 300  # Schnelltest
.venv\Scripts\streamlit run heatmap_app.py
```

**Grenzen:** Historie nutzt die heutige Index-Zusammensetzung
(Survivorship-Bias). Market Cap im Scanner ist der aktuelle Wert. Yahoo kann
einzelne Laeufe drosseln – ein ausgefallener Tag wird beim naechsten Lauf
nachgeholt (die letzten 15 Handelstage werden immer neu berechnet).

# Theme Tracker (Gruppen aus themes.csv)

Der Tab **Theme Tracker** bildet den Excel-Tracker "Theme Tracker" in der App
ab. Gruppen und Benchmarks stehen in `themes.csv` (Spalten: Theme, Role =
member/benchmark, Ticker, Name, Benchmark) und sind im Tab "Universum" oder
direkt im Repo editierbar. Die Daten kommen live von Yahoo (ein Download je
Gruppe, 10 Minuten gecacht) – unbereinigte Kurse, damit SMA- und
52-Wochen-Werte exakt zur Tabelle passen.

Je Titel: Kurs, Performance 1D/1W/2W/4W/3M/6M/12M, Ø Dollar-Volumen (63 Tage),
Trend (Anzahl der MAs unter dem Kurs), EMA10/SMA20/SMA50/SMA200, % vom
52-Wochen-Hoch mit Zone (Pivot-Zone / Leader / Mittelfeld / Angeschlagen),
ATR % und $, ATR-Extension zum SMA50 in % und in ATR-Vielfachen, die
Entry-Level SMA50 + 3 bzw. 4 ATR und die Entry-Ampel
(GO / kein Entry / extended). Darunter der **Momentum-Quadrant** (RRG) gegen
den Gruppen-Benchmark: Leading / Improving / Weakening / Lagging aus
Langfrist (Ø Rel 6M/12M) und Kurzfrist (Rel 4W), als Streudiagramm und
Tabelle. Alle Schwellen sind im Tab unter "Parameter" einstellbar.

Gegen die Excel-Datei gegengerechnet (Stand 20.10.2026, Abweichung 0,000 %):
SMA20/50/200, Performance 1D/1W/2W/4W/3M/6M/12M (4 Wochen = 21 Handelstage),
% vom 52-Wochen-Hoch, ATR (Wilder 14) und beide ATR-Extensionen. Abweichend:
`EMA10` ist der Standard-EMA (span 10) – die Excel-Spalte stammt aus einer
anderen Quelle und liegt je nach Titel bis zu 1,5 % daneben; `ATR-Veränd. %`
ist hier ATR gegen den Wert vor 21 Tagen, die Excel-Spalte liess sich nicht
reproduzieren.
