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
