# TSF-Level und Eigenbau im Vergleich

Stand 22.11.2026. Grundlage: die TSF-Blätter 2 bis 6 von 8 und die Chartbeispiele aus dem Substack-Beitrag (Screenshots), dazu `research/level_steckbriefe.py`. Abschnitt 5 stützt sich auf Screenshots eines späteren TSF-Rückblicks.

## 1. Was die TSF-Blätter zeigen

| Level | Name | Häufigkeit | Risikofenster | Kernzahl laut Blatt |
|---|---|---|---|---|
| 1 | Elevated, im Chart „Caution" | rund 6 pro Jahr | 10 Sessions | Dip ≥ 3 % in 10 Sessions: 22 % gegen 12 % |
| 2 | High, „first actionable level" | rund 2,4 pro Jahr, n = 34 | 1 bis 3 Monate | Korrektur ≥ 5 % in 45 Sessions: 32 % gegen 20 % |
| 3 | Very High | rund 1,9 pro Jahr, n = 26 | sofort, bis 1 bis 3 Monate | 38 %, bei „full alignment" 57 % |
| 4 | Extreme | rund 1 pro Jahr, n = 15 | 30 bis 60 Sessions | 67 %, bei „full alignment" 82 % (9 von 11) |

Aus den Charts lese ich zwei Ebenen:

- Auslöser: ein Dreieck über dem Balken mit „LEVEL 2" oder „LEVEL 4", bei Level 1 ein kleines Dreieck mit „LEVEL 1 CAUTION". Was sie auslöst, ist nicht veröffentlicht. Level 4 entsteht laut Blatt „under extreme conditions".
- Bestätigungen: ein rotes Kästchen unter dem Balken, zum Beispiel „LEVEL 3 · 1/3 · C", „LEVEL 3 · 2/3 · CB", „LEVEL 3 · 3/3 · VCB" oder „LEVEL 4 · 2/3 · CB". Es gibt drei Bestätigungen (V, C, B). Level 3 ist demnach ein Level 2 mit mindestens einer Bestätigung, „full alignment" heißt 3 von 3. Level 4 hat dieselben Stufen.
- Bänder: ein rotes Band läuft ab dem Signal über das Risikofenster, bei Level 1 ein schmales oranges.

Das ist meine Lesart der Bilder. TSF beschreibt die Regeln nicht.

## 2. Der Eigenbau auf denselben Kennzahlen

Zeitraum wie bei TSF, 03.01.2012 bis 31.07.2026, S&P 500. Beschreibend: mehrere Kennzahlen je Level, keine Korrektur für Mehrfachvergleiche, der Zeitraum enthält die Entwicklungsjahre. Die TSF-Zahlen stammen von den Blättern und sind nicht nachprüfbar.

Basis, bei TSF „random day near highs", beim Eigenbau alle Gate-Tage:

| Kennzahl | TSF | Eigenbau |
|---|---|---|
| Dip ≥ 3 % in 10 Sessions | 12 % | 12,4 % |
| Dip ≥ 3 % in 30 Sessions | 32 % | 30,9 % |
| Korrektur ≥ 5 % in 45 Sessions | 20 % | 20,2 % |
| Korrektur ≥ 5 % in 3 Monaten (63 Sessions) | 26 % | 25,4 % |
| Rückgang ≥ 10 % in 30 Sessions | 2,8 % | 2,4 % |
| Mittlerer tiefster Dip, 45 Sessions (Median) | −2,1 % | −2,1 % |

Die Basis stimmt auf allen sechs Kennzahlen. Das Gate (höchstens 3 % unter dem 252-Tage-Schlusshoch) trifft also dieselbe Grundgesamtheit wie „near highs" bei TSF.

Level gegen Level. Beim Eigenbau stehen zwei Lesarten: der Marker (Erstsignal, ein Ereignis wie bei TSF) und der Zustand (alle Tage mit diesem Level).

| | TSF | Eigenbau, Marker | Eigenbau, Zustand |
|---|---|---|---|
| Level 1: Dip ≥ 3 % in 10 Sessions | 22 %, rund 6 pro Jahr | 21,4 % (6 von 28), 1,9 pro Jahr | 16,6 % (722 Tage) |
| Level 2: Dip ≥ 3 % in 30 Sessions | 53 % | 23,7 % | 28,1 % |
| Level 2: Korrektur ≥ 5 % in 45 Sessions | 32 %, n = 34 | 21,1 % (8 von 38), 2,6 pro Jahr | 18,4 % (331 Tage) |
| Level 2: Korrektur ≥ 5 % in 3 Monaten | 38 % | 28,9 % | 26,0 % |
| Level 3: Korrektur ≥ 5 % in 45 Sessions | 38 %, bei 3/3 57 %, n = 26 | 28,1 % (9 von 32), 2,2 pro Jahr | Warnzustand 41,3 % (74 von 179 Tagen) |
| Level 3: mittlerer tiefster Dip | −3,7 % | −2,3 % | −3,4 % |
| Level 4: Korrektur ≥ 5 % in 45 Sessions | 67 %, bei 3/3 82 %, n = 15 | 42,9 % (6 von 14), 1,0 pro Jahr | 39,6 % (21 von 53 Tagen) |
| Level 4: Rückgang ≥ 10 % in 30 Sessions | 20 % | 0 % | 1,9 % |
| Level 4: mittlerer tiefster Dip | −6,0 % | −3,9 % | −1,8 % |

Befund:

- Die Häufigkeiten der Marker liegen nah an TSF (2,6 gegen 2,4, 2,2 gegen 1,9, 1,0 gegen 1 pro Jahr).
- Die Trefferquoten erreichen TSF auf keiner Stufe. Als Ereignis liegen Level 2 und 3 des Eigenbaus nahe an der Basis, Level 4 bei 43 % gegen 67 %.
- Nur als Zustand gelesen kommt der Warnzustand (41 %) an das TSF-Level 3 (38 %) heran. Level 4 ist beim Eigenbau nicht gefährlicher als Level 3.
- Woher der Abstand kommt, lässt sich von außen nicht entscheiden: Die Auslöser von TSF können echte Information tragen, oder die Blätter sind durch die Auswahl geschönt (über 120 verworfene Kandidaten, Era-Split zur Auswahl benutzt). Belegen kann das nur die Zeit nach dem 28.08.2026.

Voller Zeitraum 2000 bis 2026 zum Vergleich: Marker ab Level 2, 3, 4 mit 24,6 %, 28,3 % und 42,1 % bei 23,1 % Basis, Warnzustand 41,3 %.

## 3. Was der Indikator von der TSF-Darstellung übernimmt (Pine 5.0)

- Marker als Dreieck über dem Balken, darunter ein Kästchen „LEVEL n · Bestätigungen", zum Beispiel „LEVEL 3 · BRV". Marker entstehen bei jeder Hochstufung, wie die Kästchen bei TSF.
- Risikofenster als blasses Band: vom ersten Tag im Warnzustand bis 45 Sessions nach dem letzten. Darüber liegen wie bisher die Bänder des Tages.
- Tabellenzeile „Fenster": „Tag n von 45" oder „zu", für S&P 500 und NASDAQ.
- Charts und App-Tab zeigen das Fenster ebenfalls. Im Tab bleiben die Marker kompakte Kästchen mit der Level-Zahl, damit sie auf dem Telefon lesbar sind.

Das Fenster ist die Messstrecke des Backtests und kein Ausstiegssignal: Kasse im Fenster brachte 2000 bis 2026 4,9 % p. a. gegen 7,8 % Buy and Hold (Regel O2 in `BACKTEST_26J.md`).

## 4. Was sich nicht übertragen lässt

- Die Auslöser für Level 1, 2 und 4. Im Eigenbau ist das Level allein die Zahl der Bestätigungen nahe am Hoch. Ein „LEVEL 3" des Indikators ist deshalb kein TSF-Level 3.
- Die Stufen x/3. Der Eigenbau hat vier Bestätigungen (C, B, R, V), das Level ist ihre Zahl. Eine zweite Zählung daneben gäbe es nur mit einem Auslöser.
- Die Namen Elevated, High, Very High, Extreme sind seit Pine 6.0 auf Alex' Wunsch übernommen, samt eigener Farbe je Level. Das ist Benennung: Die eigenen Zahlen tragen keine vier Abstufungen, Level 1 liegt an der Basis und Level 4 nicht über Level 3. Die Tabelle des Indikators zeigt deshalb die Quote je Level neben dem Namen.
- Das kurze Level-1-Signal. Der Marker ab Level 1 kommt mit 21,4 % zwar an die 22 % von TSF heran, das sind aber 6 von 28 Fällen.

Einen eigenen Auslöser baue ich nicht ein. Für einen sauberen Test fehlen die Daten: 2007 bis 2016 waren Entwicklung, 2017 bis 2026 und 1999 bis 2007 sind verbraucht (`SPEC_v1.1.md`, kein zweiter Versuch). Ein Auslöser ließe sich nur vorwärts prüfen, als festgelegte Hypothese ab dem 21.11.2026.

## 5. Datierter Einzelfall: TSF-Level 4 vom 21.09.2026

Grundlage: Screenshots eines TSF-Rückblicks vom November 2026, der den Beitrag „Important Signals" vom 22.09.2026 zitiert. Das Signaldatum ist aus dem Beitragsdatum und der letzten Kerze des Charts abgeleitet, eine Zeitachse ist im Screenshot nicht sichtbar. Kurse: SPY-Schlusskurse aus `levels_py.csv` (dividendenbereinigt).

TSF am 21.09.2026:

- Auf der letzten Kerze sitzen die Dreiecke „LEVEL 2" und „LEVEL 4", darunter das Kästchen „LEVEL 3 · 2/3 · CB".
- Der Text nennt Level 4 „second highest warning", die Überschrift „höchste Warnstufe". Über Level 4 liegt demnach noch eine Stufe, vermutlich Level 4 mit voller Bestätigung. In den Blättern aus Abschnitt 1 ist sie nicht als eigene Stufe geführt.
- Laut Text gehören die dunkelroten Bänder zu Level 4. Im Chart folgt Dunkelrot aber auch auf „LEVEL 3 · 3/3 · VCB" ohne Level-4-Dreieck. Die Regel dahinter ist offen.

Eigenbau am selben Tag:

- Level 1, nur B. C, R und V aus. SPY schloss bei 773,50, das sind +1,6 % zum Vortag und 0,3 % unter dem 252-Tage-Schlusshoch.
- C (HYG/IEF) wurde erst am 14.10.2026 aktiv. TSF führte C am 21.09. als bestätigt.

Ergebnis auf der Kennzahl „Korrektur ≥ 5 % in 45 Sessions":

| Signal | Schluss | Ergebnis |
|---|---|---|
| TSF, Level 4, 21.09.2026 | 773,50 | Treffer: −5 % am 05.11. (Session 33), −10,8 % am 20.11. (Session 44). Das Fenster endet am 23.11. |
| Eigenbau, Marker Level 3 (BRV), 09.09.2026 | 760,51 | kein Treffer: tiefster Schluss −3,6 % am 05.11. (Session 41), Fenster zu am 11.11. |
| Eigenbau, Warnzustand, Tag 28.09.2026 | 765,61 | Treffer: −5 % am 19.11. (Session 38) |
| Eigenbau, Warnzustand, Tag 15.10.2026 | 771,79 | Treffer: −5 % am 05.11. (Session 15) |

Befund:

- Der TSF-Auslöser feuerte in einen starken Tag nahe am Hoch. Der Eigenbau zählt Risk-off-Bestätigungen und stand an dem Tag auf Level 1. Der Unterschied aus Abschnitt 4 ist damit an einem datierten Fall belegt.
- TSF definiert Credit anders als HYG/IEF gegen SMA 50 und 20-Tage-Änderung. Der Beitrag zeigt als Credit-Sicht die kumulierte A/D-Linie der High-Yield-Anleihen (SentimenTrader). Ob sie in C steckt, ist nicht belegt.
- Der eigene Marker vom 09.09. war nach der eigenen Kennzahl ein Fehlsignal. Als Zustand gelesen trafen die späteren Warntage.
- Es ist ein Fall, und TSF hat ihn im Rückblick selbst ausgewählt. Er zählt als erster Treffer nach der Veröffentlichung der Blätter (28.08.2026) und ändert das Urteil „nicht belegt" für den Eigenbau nicht.

Weitere Signale aus dem Beitrag, nicht eingebaut:

- RSP mindestens 2 ATR über der EMA 21 („usually tops"). Mit freien Daten rechenbar.
- Verhältnis S&P High Beta zu S&P High Quality, Rang (SentimenTrader). Mit SPHB/SPHQ annähernd rechenbar, das Rangfenster ist nicht genannt.
- Steiler Anstieg in Consumer Staples (XLP). Verwandt mit R, aber eine andere Größe.
- Kumulierte A/D-Linie der High-Yield-Anleihen und „Hedgers Combo": SentimenTrader-Daten, nicht frei verfügbar.

Alle wurden nach dem Einbruch gezeigt. In die eingefrorene v1.1 gehören sie nicht.

Die beiden rechenbaren Signale sind in `TSF_POST_SIGNALE.md` über die Historie geprüft, mit vorab festgelegter Regel und einem Lauf. Ergebnis: RSP überdehnt liegt mit 19,5 % unter der Basis von 21,9 % und verschlechtert den Warnzustand. Die Flucht aus High Beta kam seit 2011 zweimal vor. Keines der beiden zählt ins Level.
