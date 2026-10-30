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

# Swing-Trading-Ansatz (nach Steve Jacobs' Praesentation, Okt. 2026)

Aus der Praesentation "Swing Trading Approach" sind vier Bausteine in die
App eingeflossen. Alles davon laeuft ueber den Nachtlauf bzw. den normalen
Yahoo-Abruf – kein neuer Datenlieferant.

## Market Metrics und Breadth-Score (Breadth-Tab)

Der Nachtlauf liefert jetzt die Kennzahlen der Folie "Market Metrics -
Summary" je Universum: Anteil ueber Eroeffnung, positive Performance ueber
Woche/Monat/Quartal/Halbjahr/Jahr, Kurs zu EMA10/EMA20/SMA20/SMA50/SMA200,
MA-Reihenfolgen (EMA10 >= EMA20, SMA20 >= SMA50, SMA50 >= SMA200, volle
Reihe), neue 20-Tage-Hochs/-Tiefs und Lage in der 20-Tage-Spanne. Neue
Universen: Nasdaq 100 (= QQQE-Logik), Dow Jones 30, S&P 500 + Nasdaq 100 +
Dow und "Market Cap ab 1 Mrd $" (Jacobs' $1B+-Universum). Die Listen fuer
Nasdaq 100 und Dow kommen aus `idx_nasdaq100.csv` / `idx_dow.csv`.

Oben im Breadth-Tab stehen vier Score-Karten wie auf der Folie (Nasdaq 100,
S&P 500, Kern, $1B+) plus ein Vorschlag fuers Risiko je Trade.
**Der Score ist eine eigene Konstruktion** – Jacobs veroeffentlicht seine
Formel nicht: Mittel aus % ueber EMA10, EMA20, SMA50, SMA200, EMA10 >= EMA20,
SMA50 >= SMA200, Monat positiv und obere Haelfte der 20-Tage-Spanne, 0-100.
Ab 60 Risk-on (volle Vorgabe), 40-60 neutral (halbe), unter 40 Risk-off
(ein Viertel). Die Vorgabe (Standard 1,00 %) ist im Tab einstellbar. Die
komplette Above/Below-Tabelle der Folie steht im Aufklappbereich "Market
Metrics".

## Industrie-RS – "One Rule To Rule Them All" (Scanner)

Jacobs' wichtigster Backtest-Befund: Jede Strategie wurde 2011-2026 in jedem
Jahr besser, wenn nur Titel aus der oberen Haelfte der Industrien nach
relativer Staerke zugelassen waren. Der Nachtlauf berechnet dafuer je
Industrie (Zuordnung aus `data/universe/master.csv`, mindestens 3 Titel) den
Median der Mitglieder-Performance ueber 1W/1M/3M/6M/1Y, rankt jede Spalte als
Perzentil 1-99 ueber alle Industrien und bildet daraus Ind-RS (Mittel der
Raenge 1W/1M/3M/6M, erneut gerankt). Ergebnis in `data/industry_rs.csv`,
je Titel als Spalte `IndRS` im Snapshot.

`scanner_config.json` hat dafuer `min_industry_rs`, **Standard 50** – also
genau Jacobs' Regel. Damit aendert sich die gespeicherte Scanner-Liste.
Wer das nicht will, setzt den Wert auf null. Im Scanner-Tab gibt es den
Filter "Industrie-RS min", die Spalte "Ind-RS" und die Industrie-Tabelle im
Aufklappbereich. Wie die Market Cap ist der Industrie-RS ein heutiger Wert;
die Scanner-Historie ist rueckwirkend nicht danach gefiltert.

## Stage-Analyse mit Jacobs' Unterphasen (Sector-Map, Stock Map)

Die Unterphasen heissen jetzt wie in der Praesentation und folgen messbaren
Regeln: 1A Upward Pivot, 1B Mean Reversion (ueber SMA50), 2A Bullish Trend,
2B Breakout Confirm (neues 20-Tage-Hoch), 2C Extended Bullish (>= 3 ATR ueber
EMA10), 3A Bullish Fade (haelt SMA50), 3B Fade Confirmation, 4A Bearish
Trend, 4B Breakdown Confirm (neues 20-Tage-Tief), 4C Extended Bearish.
Hauptstufe unveraendert nach Weinstein. Bullish = Stage 1 + 2.

Unter der Sector-Map und der Stock Map steht das Dashboard der Folien
"Stage Analysis": Verteilung je Unterphase, Bullish/Bearish-Balken und je
Unterphase die Titel mit 1D %. Die Stock Map laedt dafuer 2 Jahre statt 6
Monate (SMA200) und hat einen Stage-Filter – Jacobs' "Watchable" waeren
z.B. die Stages 1A bis 2B.

## Sektor-Rotation (Sector-Map)

Wie auf der Folie "Sector Relative Strength": die 11 SPDR-Sektoren als
Perzentilrang ihrer Wochen- (5 Tage) gegen Monatsperformance (21 Tage),
Quadranten Strong / Improving / Weakening / Weak. Jacobs' Hinweis dazu:
Strong schlaegt Improving – "leading stocks in leading groups".

## Nicht umgesetzt

Entry-Regeln (Kauf zum Schluss, Pilot-Position, Scale-in), Stops und
Gewinnmitnahme ab 7x ATR vom SMA50 sind Handelsregeln, keine App-Funktion;
die 7x-Schwelle steckt bereits in der Ampel des Theme Trackers.
Backtesting, Modelling und Pinescreener liegen ausserhalb einer
Streamlit-Anzeige. Candle-Faerbung nach Stage im Detail-Chart waere der
naechste sinnvolle Schritt.
