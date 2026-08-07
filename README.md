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
