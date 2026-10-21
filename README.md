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

## Tempo

Die Ansichten werden ueber eine Auswahlleiste umgeschaltet, nicht ueber
`st.tabs`: Streamlit fuehrt bei jedem Rerun alle Tab-Bloecke aus, auch die
unsichtbaren – mit einem Yahoo-Download in fast jedem Block dauerte ein
Durchlauf rund 80 Sekunden. Jetzt laeuft nur der sichtbare Block.

Weitere Bremsen entfernt: Auto-Refresh steht standardmaessig auf "Aus"
(vorher 60 s, was den 60-Sekunden-Cache bei jedem Lauf verfallen liess),
Kursdaten werden 5 statt 1 Minute zwischengespeichert, Kurse und
RVOL/ATR teilen sich einen Download statt zweier, und die Market Caps
laufen ueber einen kleinen Thread-Pool statt nacheinander.

Gemessen: Erststart 15-17 s (vorher ~80 s), jeder weitere Wechsel 0,1-6 s,
erneuter Aufruf derselben Ansicht 0,2-0,3 s. Breadth und Scanner lesen nur
Dateien und sind sofort da.

Bekannt und rein optisch: leere Zahlenzellen zeigt Streamlit in gestylten
Tabellen als "None" statt "–" (betrifft Titel ohne ausreichende Historie).

## IBKR-Verbindung

Der IBKR-Umschalter funktioniert **nur lokal**: TWS bzw. IB Gateway laeuft auf
dem eigenen Rechner und ist aus der Streamlit-Cloud nicht erreichbar. In der
Cloud blendet die App die Auswahl deshalb ganz aus und nutzt immer Yahoo.
Erkannt wird der Cloud-Betrieb am Pfad `/mount/src`; `HEATMAP_CLOUD=1`
erzwingt ihn (zum Testen oder wenn die Erkennung mal nicht greift).

Lokal noetig:
1. `pip install ib_async` (steht in requirements.txt, fehlt aber in einer
   bestehenden venv leicht)
2. TWS oder IB Gateway starten und einloggen
3. Dort unter **Einstellungen -> API -> Settings** den Haken bei
   *Enable ActiveX and Socket Clients* setzen
4. Port passend waehlen: 7496 live, 7497 Paper, 4001/4002 Gateway

Die Seitenleiste prueft den Port vorab und nennt die Ursache, statt in einen
langen Timeout zu laufen. **Pacing beachten:** IBKR erlaubt nur rund 60
Historien-Abrufe je 10 Minuten, die App braucht einen je Ticker – grosse
Universen laufen in die Sperre. Das Ergebnis wird deshalb zwischengespeichert.

# Stage-Analyse (Sector-Map)

Jeder Titel der Sector-Map bekommt eine Stage nach Weinstein, mit Unterphase
in Anlehnung an Oliver Kells "Cycle of Price Action". Sie steht als farbige
Spalte in der Tabelle, im Tooltip der Kachel und unter dem Detail-Chart;
darunter die Verteilung ueber das ganze Universum.

**Hauptstufe** aus Kurs und SMA200 samt dessen 20-Tage-Steigung
(Tagesvariante der 30-Wochen-Linie):

| Stufe | Bedingung |
|---|---|
| 2 Advancing | Kurs ueber steigendem SMA200 |
| 3 Distribution | Kurs ueber SMA200, Steigung flach oder negativ |
| 4 Declining | Kurs unter fallendem SMA200 |
| 1 Basing | Kurs unter SMA200, Steigung nicht mehr fallend |

**Unterphase** aus der Kurslage, mit `ext10 = (Kurs - EMA10) / ATR14`:
2C ab ext10 >= 3 (Exhaustion), 2B ueber SMA50, 2A darunter (Ruecksetzer);
3A haelt den SMA50, 3B darunter; 4C ab ext10 <= -3 (Kapitulation), 4A erst
<= 25 Tage unter SMA200, sonst 4B; 1B ueber SMA50 mit EMA10 ueber EMA20
(Wedge Pop), sonst 1A.

Ehrliche Einordnung: Die Hauptstufe ist messbar und folgt Weinstein. Kells
Unterphasen sind eigentlich Chartmuster (Wedge Pop, Base 'n Break, Exhaustion
Extension) – mechanisch nicht sauber erkennbar. Der Buchstabe steht hier
deshalb fuer die Kurslage zu SMA50/EMA10: gut zum Sortieren und Filtern,
kein Ersatz fuer den Blick auf den Chart.

Dafuer laedt die App 2 Jahre Historie statt 6 Monate (SMA200 braucht 200
Tage). Das kostet praktisch keine Zeit – gemessen 10,3 s gegen 10,5 s, weil
die Anzahl der Abrufe gleich bleibt.

# Ansichten

Sector-Map (frueher "Aktien / ETF") und Stock Map (frueher "Index-Maps").
Die Stock Map filtert zusaetzlich nach Groessenklasse, bevor sie laedt –
das spart bei S&P 500 und Small Caps spuerbar Zeit:

| Klasse | Market Cap |
|---|---|
| Small Cap | 300 Mio bis 2 Mrd |
| Mid Cap | 2 bis 10 Mrd |
| Large Cap | 10 bis 200 Mrd |
| Mega Cap | ab 200 Mrd |

Die Market Caps stammen aus `data/universe/master.csv` (taeglicher Lauf),
kosten also keinen zusaetzlichen Abruf. Abdeckung: S&P 500 und Nasdaq 100
rund 100 %, Small Caps rund 90 %; Titel ohne Wert bleiben ungefiltert und
werden in der Fusszeile ausgewiesen.

Die Ansichten **Watchlist** und **Gate-Check** sind entfallen. Damit wurden
auch `compute_ibd_rs`, `fetch_universe_ohlcv` und `compute_breadth`
ueberfluessig (Letzteres war seit dem Breadth-Umbau ohnehin tot).
`watchlist.csv` und `rs_universe.csv` bleiben im Repo, werden aber nicht
mehr gelesen.
