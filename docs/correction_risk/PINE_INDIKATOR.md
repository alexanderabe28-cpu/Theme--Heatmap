# Pine-Indikator „Correction Risk v1.1 (Schattenmodus)"

Stand 22.11.2026. Datei `correction_risk.pine` (Pine v6), in TradingView gespeichert als Version 6.0.

Versionen: 1.0 erste Fassung, 2.0 Deckkraft der Bänder, 3.0 Level-Marker, 4.0 Marker mit Tooltip und Bestätigungen, Zeile „Quote / Basis", Alerts, Bänder im Wochenchart, 5.0 Darstellung nach den TSF-Charts: Dreieck mit Kästchen „LEVEL n · Bestätigungen", Risikofenster als Band, Zeile „Fenster", 6.0 Abstufung mit den TSF-Namen: 1 ELEVATED (gelb), 2 HIGH (orange), 3 VERY HIGH (rot), 4 EXTREME (violett) für Säulen, Bänder, Marker, Tabelle und Alerts. Die Zeile „Quote / Basis" zeigt seitdem die Quote je Level: S&P 500 18,6 / 24,8 / 27,8 / 42,2 / 38,3 % bei 23,1 % Basis, NASDAQ 29,1 / 35,3 / 37,9 / 39,5 / 53,1 % bei 32,5 % Basis (Level 0 bis 4). Die Namen sind auf Wunsch übernommen. Beim S&P 500 liegt ELEVATED an der Basis und EXTREME nicht über VERY HIGH. Ältere Abschnitte unten nennen noch die Farben vor 6.0. Prüfung 6.0: Band je Woche über 56 Wochen ab 27.10.2025 (AMEX:SPY, Wochenchart) und Level am Wochenschluss stimmen mit dem Python-Modell überein, einschließlich der beiden Wochen mit Level 4. Der Vergleich mit den TSF-Blättern steht in `LEVEL_VERGLEICH_TSF.md`.

## Was er zeigt

- Säulen im eigenen Fenster: Zahl der Bestätigungen (0–4). Orange = Warnzustand (Gate an, mindestens 3), gelb = Gate an und 2, blau = Gate an und 0 bis 1, grau = außerhalb des Gates, also kein Level.
- Leiste am unteren Rand des Fensters: Gate an. Ohne Säule darüber heißt das Level 0.
- Bänder im Kurschart: orange im Warnzustand, gelb bei 2 Bestätigungen.
- Risikofenster: blasses Band im Kurschart und in der Leiste, vom ersten Tag im Warnzustand bis 45 Sessions nach dem letzten. Es ist die Messstrecke des Backtests und kein Ausstiegssignal (Regel O2: 4,9 % p. a. gegen 7,8 % Buy and Hold). Die Tabellenzeile „Fenster" zeigt „Tag n von 45" oder „zu".
- Level-Marker im Kurschart: Dreieck über dem Balken und darunter ein Kästchen „LEVEL n · Bestätigungen" (bis Version 4.0 ein Kästchen mit der Level-Zahl über dem Balken) am ersten Tag, an dem das Level höher ist als an den 20 Sessions davor. Das ist das Erstsignal aus Spec v1.0 (`episode_starts` mit `episode_gap = 20`). Voreingestellt ab Level 2, einstellbar von 1 bis 4. Gelb = 2, orange = 3 und 4. Der Tooltip nennt Datum, Level, Bestätigungen und Abstand zum Hoch. Die Buchstaben C B R V stehen am Marker, mit der Eingabe „Bestätigungen am Marker" lassen sie sich abschalten. Die Marker sind Labels, TradingView zeigt davon höchstens 500. Im Testlauf waren es 85 seit 2007.
- Tabelle: Level, Abstand zum 252-Tage-Schlusshoch, Bestätigungen, der jüngste Marker und „Quote / Basis" für S&P 500 und NASDAQ nebeneinander. „Quote / Basis" ist die eingefrorene Quote des aktuellen Zustands 2000–2026 (Rückgang von mindestens 5 % binnen 45 Sessions) und die Basis aller Gate-Tage: S&P 500 20,8 / 27,8 / 41,3 % bei 23,1 % Basis, NASDAQ 31,0 / 37,9 / 43,5 % bei 32,5 % Basis, jeweils für Level 0–1, 2 und ab 3. Außerhalb des Gates steht ein Strich.
- Alerts über `alert()`: neuer Marker ab der gewählten Schwelle und Beginn des Warnzustands, für den Index des Charts, zum Balkenschluss. Sie wirken erst, wenn in TradingView ein Alert auf die alert()-Aufrufe des Skripts angelegt ist. Der Text endet mit „Schattenmodus, kein Handelssignal".
- Datenfenster: Level und Gate beider Indizes, Abstand zum Hoch, die vier Bestätigungen einzeln, Erstsignal beider Indizes.

Folge der Marker-Regel: Eine Warnphase bekommt keinen eigenen Marker, wenn das Level in den 20 Sessions davor schon so hoch war. Beispiel S&P 500 im Herbst 2026: Marker 3 am 09.09., die Warnphase vom 15.10. bis 30.10. hat keinen neuen Marker, weil Level 3 zuletzt am 29.09. anlag. Die Bänder zeigen jede Phase.

Im Wochenchart sitzt der Marker in der Woche des Signals. Fallen zwei Signale in eine Woche, zeigt er das spätere, das immer das höhere ist. Die Bänder färben in Wochen- und Monatscharts jeden Balken, der mindestens einen Tag im Warnzustand (orange) oder mit 2 Bestätigungen (gelb) enthält. Säulen und Tabelle zeigen dort den Stand am Balkenschluss.

Eingabe „Index für Säulen und Bänder": Auto wählt auf NASDAQ-Charts (QQQ, QQQM, TQQQ, ONEQ, NDX, IXIC, NDQ, NAS100, US100, USTEC, NQ, MNQ) die NASDAQ-Variante, sonst das S&P-500-Modell. Die Parameter des Modells sind keine Eingaben, sie sind eingefroren.

## Daten

- Tagesschlusskurse, dividendenbereinigt über `ticker.modify(..., adjustment = adjustment.dividends)`, damit sie zu den Yahoo-Reihen des Backtests passen. Das ist bei HYG/IEF nötig, weil die Ausschüttungen das Vorzeichen der 20-Tage-Veränderung drehen können.
- Gerechnet wird im Tageskontext von SPY über verschachtelte `request.security`-Aufrufe. Der Indikator liefert deshalb auf jedem Zeitrahmen dieselben Tageswerte. Im Wochenchart zählt der Stand am Wochenschluss.
- VIX: Der Tagesbalken von CBOE:VIX schließt um 16:15 ET, der von SPY um 16:00 ET. Ohne `lookahead` liefert Pine im Verlauf den VIX-Schluss des Vortags. Das Script holt den VIX deshalb mit `barmerge.lookahead_on`. Am Tag t steht damit der VIX-Schluss von t, wie im Backtest. Am laufenden Tag ist der Stand vorläufig.
- Verlauf ab Juni 2007, weil HYG erst seit April 2007 handelt. Die Ersatzreihen des 26-Jahre-Laufs gibt es in TradingView nicht.
- Auf Charts mit früherem Handelsschluss als New York erscheint der Stand einen Tag später.

## Abgleich mit dem Python-Modell

Testlauf über den TradingView-Connector auf AMEX:SPY, Tageschart, 500 Handelstage vom 22.11.2024 bis 20.11.2026. Verglichen wurden je Tag die vier Bestätigungen und beide Gates mit `levels_py.csv` aus `research/nasdaq_variante.py`.

| | Ergebnis |
|---|---|
| Erste Fassung ohne `lookahead` beim VIX | 69 von 500 Tagen abweichend: 68 bei V, dort um einen Tag versetzt, und 1 bei Credit |
| Fassung mit `lookahead` beim VIX | 1 von 500 Tagen abweichend |
| Abweichender Tag | 27.08.2025, Credit: HYG/IEF lag bei Yahoo 0,0004 % unter der SMA50, bei TradingView darüber |
| Tage im Warnzustand, S&P 500 | 51 in Pine, 51 in Python |
| Tage im Warnzustand, NASDAQ | 12 in Pine, 12 in Python |
| Abstand zum Hoch am 20.11.2026 | −11,4595 % und −19,9050 % in beiden |

Level-Marker (Version 3.0), gleicher Testlauf über 500 Handelstage:

| | Pine | Python |
|---|---|---|
| Marker S&P 500, alle Level | 15 | 15 |
| Marker S&P 500, ab Level 2 | 12 | 12 |
| Marker NASDAQ, alle Level | 14 | 14 |
| Marker NASDAQ, ab Level 2 | 9 | 9 |
| Die letzten 8 Marker je Index, Datum und Level | alle 16 identisch | |

Im Wochenchart von AMEX:SPY erscheint der Marker 3 in der Woche ab 08.09.2026, auf NASDAQ:NDX im Tageschart die Marker 2 am 22.09. und 3 am 28.09.2026, wie im Python-Modell.

Version 4.0, gleicher Testlauf und zwei Wochenläufe:

| | Pine | Python |
|---|---|---|
| Abweichende Tage in 500 (Bestätigungen, Gates) | 1 | wie zuvor, 27.08.2025 |
| Tage mit orangem Band, S&P 500 | 51 | 51 |
| Tage mit gelbem Band, S&P 500 | 53 | 53 |
| Jüngster Marker S&P 500 | 09.09.2026, Level 3, B R V, −1,9900 % zum Hoch | identisch |
| Jüngster Marker NASDAQ | 28.09.2026, Level 3, B R V, −1,4623 % zum Hoch | identisch |
| Band je Woche, AMEX:SPY, 12 Wochen ab 31.08.2026 | 0 3 3 2 3 2 3 3 3 3 2 0 | identisch |
| Band je Woche, NASDAQ:NDX, dieselben Wochen | 0 0 0 2 3 2 2 0 0 0 0 0 | identisch |

Version 5.0, gleicher Testlauf:

| | Pine | Python |
|---|---|---|
| Abweichende Tage in 500 (Bestätigungen, Gates) | 1 | wie zuvor, 27.08.2025 |
| Marker, Bänder | unverändert | unverändert |
| Tage im Risikofenster in 500, S&P 500 | 244 | 244 |
| Tage im Risikofenster in 500, NASDAQ | 194 | 194 |
| Stand 20.11.2026, S&P 500 | Tag 12 von 45 (letzter Warntag 04.11.2026) | identisch |
| Stand 20.11.2026, NASDAQ | Tag 38 von 45 (letzter Warntag 29.09.2026) | identisch |
| Fenster-Tag je Wochenschluss, 10 Wochen ab 14.09.2026, NASDAQ:NDX im Wochenchart | S&P 500: 3 8 3 8 0 0 0 2 7 12, NASDAQ: zu zu 3 8 13 18 23 28 33 38 | identisch |

Zusätzlich gerechnet und mit den letzten 12 bis 30 Tagen des Python-Modells verglichen: SP:SPX, NASDAQ:NDX, NASDAQ:IXIC und NASDAQ:QQQ im Tageschart sowie AMEX:SPY im Wochenchart. Alle stimmen überein, Auto wählt auf NDX, IXIC und QQQ das NASDAQ-Gate.

Nicht geprüft: die Optik in TradingView und das Auslösen der Alerts. Der Connector rechnet Werte und zeichnet keinen Chart. Tabelle, Farben, Bänder und Marker sind dort ungesehen, die Alerts sind nur kompiliert.

## Charts

`charts/correction_risk_sp500.png` und `charts/correction_risk_nasdaq.png` stammen aus `research/charts_pine.py`: Index-Schlusskurse von Yahoo (^GSPC, ^NDX) und die Modellzustände, die im gezeigten Fenster (10.11.2025 bis 20.11.2026) mit der Pine-Ausgabe übereinstimmen. Es sind keine TradingView-Screenshots.

## Bewusst nicht enthalten

Strategie-Logik, ein Live-Zähler (den führt der App-Tab) und eine Gate-Linie im Kurs. Die Marker sind als Einzelsignal nicht belegt (Zahlen in `NASDAQ_VARIANTE.md`, Abschnitt 3). Das Modell ist nicht belegt und hat keine Autorität über Entscheidungen. Die NASDAQ-Variante ist schwächer als das S&P-Modell, siehe `NASDAQ_VARIANTE.md`.
