# NASDAQ-Variante des Correction-Risk-Modells

Stand 22.11.2026. Abschnitt 1 wurde vor dem Lauf geschrieben, Abschnitt 2 danach angehängt.

## 1. Festlegung vor dem Lauf

Anlass: Der Pine-Indikator soll neben dem S&P 500 auch den NASDAQ zeigen. Das Modell v1.1 ist nur mit SPY als Gate getestet. Damit das NASDAQ-Feld nicht ohne Zahlen dasteht, wird die naheliegendste Übertragung einmal ausgewertet.

Definition, unverändert aus v1.1 bis auf den Index:

- Gate N: QQQ schließt höchstens 3 % unter seinem 252-Tage-Schlusshoch (bereinigte Schlusskurse).
- Bestätigungen C, B, R, V wie in v1.1. Sie messen den Gesamtmarkt und werden nicht durch NASDAQ-eigene Reihen ersetzt (kein VXN, kein gleichgewichteter NASDAQ-100). Vor 2007 gelten dieselben Ersatzreihen wie im 26-Jahre-Lauf.
- Level N = Zahl der Bestätigungen an Gate-N-Tagen, Warnzustand N = Level N ≥ 3.
- Ziel: tiefster QQQ-Schluss in t+1 … t+45 liegt mindestens 5 % unter Schluss t. Zensierung wie bisher. Nebenziel: mindestens 8 %, weil der NASDAQ stärker schwankt.
- Fenster: erster Tag mit definiertem Gate N (erwartet März 2000, QQQ handelt seit 10.03.1999) bis 20.11.2026.

Ausgaben:

1. Quote je Level, Warnzustand gegen Gate-Basis, zirkulärer Shift-Test über die Gate-Tag-Folge (Versatz mindestens 60).
2. Dieselben Quoten für die drei Zeiträume bis 19.06.2007, bis 30.12.2016 und ab 03.01.2017.
3. Verteilung der Warntage und Treffer auf Jahre.
4. QQQ-Korrekturen von mindestens 5 % ab 252-Tage-Hoch: Anteil mit Warnzustand zwischen 20 Sessions vor dem Hoch und dem Vortag des ersten −5-%-Schlusses, verglichen mit dem Zufall nur über Gate-Tage. Zusätzlich der Anteil, bei dem der Warnzustand spätestens am Tag des Hochs anlag.

Regeln:

- Ein Lauf. Kein Parameter wird geändert, keine zweite Variante wird nachgeschoben, egal wie das Ergebnis ausfällt.
- Der Lauf beschreibt. Er enthält die Entwicklungsjahre 2007–2016 der Bestätigungen und ist kein Test. Die NASDAQ-Variante startet deshalb wie das S&P-Modell im Schattenmodus.

## 2. Ergebnis (Lauf vom 22.11.2026, `research/nasdaq_variante.py`)

Fenster 07.03.2000 bis 20.11.2026, 6 719 Handelstage. Gate N an 43,5 % der Tage, 2 926 Gate-Tage mit bekanntem Ausgang.

| | NASDAQ-Variante (Gate und Ziel QQQ) | S&P 500 (v1.1, 26-Jahre-Lauf) |
|---|---|---|
| Basisrate, Ziel 5 % | 32,5 % | 23,1 % |
| Quote Level 0 / 1 / 2 / 3 / 4 | 29,1 / 35,3 / 37,9 / 39,5 / 53,1 % | 18,6 / 24,8 / 27,8 / 42,2 / 38,3 % |
| Warnzustand | 168 Tage, 43,5 %, Shift-p 0,078 | 247 Tage, 41,3 %, Shift-p 0,004 |
| Mindestens 2 Bestätigungen | 487 Tage, 39,8 %, p 0,065 | 743 Tage, 32,3 %, p 0,007 |
| Ziel 8 %: Warnzustand gegen Basis | 29,8 % gegen 18,3 %, p 0,055 | nicht gerechnet |

Warnzustand je Zeitraum, Ziel 5 %:

| Zeitraum | Tage | Quote | Basis | Shift-p |
|---|---|---|---|---|
| 07.03.2000 – 19.06.2007 (Ersatzreihen) | 15 | 20,0 % | 30,0 % | 0,786 |
| 20.06.2007 – 30.12.2016 (Entwicklungsjahre) | 92 | 55,4 % | 33,4 % | 0,048 |
| ab 03.01.2017 | 61 | 31,1 % | 32,5 % | 0,550 |

Korrekturen des QQQ von mindestens 5 % ab 252-Tage-Hoch: 47, davon 26 mit mindestens 10 %.

- Warnzustand vor dem ersten −5-%-Schluss: 22 von 47, Zufall nur über Gate-Tage 16,4 (5–95 %: 12–21), p 0,024.
- Warnzustand spätestens am Tag des Hochs: 13 von 47.
- Mindestens 2 Bestätigungen: 33 von 47, Zufall 32,1, p 0,43.
- Ohne Warnung blieben 13 der 26 Korrekturen ab 10 %, darunter 2018 (−22,8 %), 2006 (−17,3 %) und 2004 (−15,9 %).

Größte Jahresbeiträge zum Warnzustand: 2015 (24 Tage, 21 Treffer), 2014 (30 / 13), 2007 (23 / 11). 2017 lieferte 26 Warntage ohne Treffer.

Befund: Die NASDAQ-Variante ist schwächer als das S&P-Modell. Der Vorsprung des Warnzustands stammt aus den Entwicklungsjahren 2007–2016, seit 2017 liegt die Quote auf Höhe der Basis. Sie ist nicht belegt und läuft im Indikator nur als zweite Anzeige im Schattenmodus. Eine zweite Variante wird nicht gebaut.

Zum Vergleich aus dem 26-Jahre-Lauf, ohne neue Definition: Der Warnzustand des S&P-Modells (Gate auf SPY) hatte auf den QQQ bezogen eine Quote von 47,8 % gegen 33,7 % Basis.

Stand 20.11.2026: Alle vier Bestätigungen an, beide Gates aus. SPY schließt 11,5 % unter seinem 252-Tage-Hoch, QQQ 19,9 %. Das Modell gibt für beide Indizes kein Level aus.

## 3. Nachtrag: Erstsignale, die Grundlage der Level-Marker

Nach dem Lauf gerechnet, weil der Pine-Indikator Level-Marker bekommen hat. Ein Marker ist ein Erstsignal nach Spec v1.0: der erste Tag mit Level ≥ k nach 20 Sessions darunter. Ziel wie oben, Rückgang von mindestens 5 % binnen 45 Sessions. Beschreibend, kein Test.

| Schwelle | S&P 500, 03.01.2000–20.11.2026 | NASDAQ-Variante, 07.03.2000–20.11.2026 |
|---|---|---|
| Basis (alle Gate-Tage) | 23,1 % | 32,5 % |
| Erstsignale ab Level 2 | 15 von 61 (24,6 %) | 17 von 48 (35,4 %) |
| Erstsignale ab Level 3 | 13 von 46 (28,3 %) | 13 von 30 (43,3 %) |
| Erstsignale ab Level 4 | 8 von 19 (42,1 %) | 5 von 8 (62,5 %) |

Einordnung: Der einzige echte Test dieser Lesart ist der aus v1.0 (S&P 500, 2007–2026). Dort bestand keine Schwelle: ab Level 3 10 von 35 (p = 0,334), ab Level 4 7 von 15 (p = 0,039, fällt durch die BH-Korrektur). Die Marker zeigen also, wann ein Level beginnt. Als Einzelsignal sind sie nicht belegt, und die Fallzahlen ab Level 4 sind klein.
