# Correction-Risk-Modell – Spec v1.1

Eingefroren am 22.11.2026 nach der Entwicklung auf E (2007–2016) und **vor** dem Lauf auf H1 (2017–2026) und H2 (1999–2007).
Grundlage: `PROTOKOLL_v1.1.md`.

## 1. Ergebnis der Entwicklung (nur E, 1 259 Gate-Tage, Basisrate 27,2 %)

### Komponenten einzeln (Tagesquote, wenn die Komponente an einem Gate-Tag wahr ist)

| Komponente | wahr an | Quote | Lift | Shift-p |
|---|---|---|---|---|
| C Credit | 21,0 % | 44,2 % | 1,63 | 0,001 |
| B Breadth | 8,6 % | 46,3 % | 1,70 | 0,030 |
| R Rotation | 23,6 % | 33,3 % | 1,23 | 0,211 |
| V Volatility | 20,7 % | 28,8 % | 1,06 | 0,382 |
| S Small Caps (neu) | 13,7 % | 35,5 % | 1,31 | 0,192 |
| F Financials (neu) | 38,2 % | 22,9 % | 0,84 | 0,807 |
| D Sektorbreite (neu) | 8,9 % | 29,5 % | 1,08 | 0,414 |

### v1.0-Zähler: Zustand gegen Erstsignal

| Schwelle | Zustand (Tage, Quote, Shift-p) | Erstsignal | VIX-Benchmark gleicher Häufigkeit |
|---|---|---|---|
| Level ≥ 1 | 571 Tage, 31,2 %, p = 0,146 | 6/18 | – |
| Level ≥ 2 | 247 Tage, 40,1 %, p = 0,025 | 6/19 | 30,0 % |
| Level ≥ 3 | 89 Tage, 52,8 %, p = 0,019 | 5/15 | 19,1 % |
| Level ≥ 4 | 23 Tage, 73,9 %, p = 0,036 | 5/7 | – |

Das VIX-Niveau allein sortiert schlecht (Quote je VIX-Quintil: 20,6 / 13,7 / 31,6 / 40,9 / 29,4 %).

### Kreuzvalidierung (Leave-one-year-out, Log-Loss, kleiner ist besser)

| Kandidat | CV-Log-Loss | gegen Zähler n4 |
|---|---|---|
| Konstante (M0) | 0,6845 | +0,0065 |
| **Zähler n4 (v1.0-Score)** | **0,6781** | – |
| M3 logVIX + n4 | 0,6756 | −0,0024 |
| M1 logVIX | 0,6912 | +0,0131 |
| M2 logVIX + dist_high | 0,7000 | +0,0219 |
| M4 logVIX + n7 | 0,6929 | +0,0148 |
| M5 logVIX + n4s (geglättet) | 0,6858 | +0,0077 |
| M6 logVIX + n7s | 0,7031 | +0,0250 |
| M7 logVIX + nSel | 0,6894 | +0,0113 |
| M8 logVIX + dist_high + n7 | 0,7005 | +0,0224 |
| nSel ohne VIX (verschachtelt) | 0,6940 | +0,0159 |
| K4 vier Einzelgewichte | 0,7066 | +0,0286 |
| K5 sieben Einzelgewichte | 0,7564 | +0,0783 |

## 2. Abweichung vom Protokoll (vor dem Holdout, nur mit E-Daten begründet)

Die gepaarte 1-SE-Regel aus Abschnitt 6 des Protokolls wählte mechanisch **M1 (nur logVIX)**. M1 ist in der Kreuzvalidierung aber
schlechter als die Konstante und in E nicht einmal monoton kalibriert. Ursache: Die Basisraten der Folds schwanken zwischen 3 % und 100 %,
dadurch ist fast jedes Modell „gleichwertig", und die Regel greift dann zum einfachsten. Die Konstante und der v1.0-Score standen nicht in der Auswahlmenge.

Entscheidung (Ermessen, dokumentiert): Die Regel wird nicht angewandt. Gewählt wird der **Zähler n4 ohne Zusatzmerkmal**.
- M3 ist nur 0,0024 besser und verschlechtert die Trennschärfe innerhalb der Jahre (mittlere Fold-AUC 0,42 gegen 0,53).
- Für logVIX gibt es in E keinen eigenen Beleg (M1 schlechter als M0).
- Gewichte, neue Komponenten, Glättung und datengetriebene Auswahl sind alle schlechter als der einfache Zähler.

Nachträglich auf E gerechnet und **nicht** übernommen: C+B als Zweier-Zähler (CV 0,6756). Die Auswahl stammt aus denselben Daten,
die verschachtelte Variante derselben Idee (nSel) ist schlechter.

## 3. Eingefrorenes Modell v1.1

- **Signale:** unverändert v1.0. Gate, C, B, R, V, Level = Zahl der wahren Komponenten an Gate-Tagen.
- **Lesart (neu):** Das Level ist ein **Zustand**. Bewertet wird jeder Tag, an dem das Level anliegt, nicht nur der erste.
- **Wahrscheinlichkeit (neu):** p = 1 / (1 + exp(1,2607 − 0,3398 · Level)), auf E geschätzt.
  Level 0: 22,1 % · Level 1: 28,5 % · Level 2: 35,9 % · Level 3: 44,0 % · Level 4: 52,5 %.
- Weil der Score nur fünf Werte annimmt, entfallen die Quantilsbänder aus Protokoll-Abschnitt 7. Level = Zählwert.

## 4. Tests (je einmal auf H1 und H2)

- **T1:** Brier(v1.1) < Brier(Konstante = Basisrate der Stichprobe), Block-Bootstrap (60 Sessions, 5 000 Ziehungen), einseitig.
- **T2:** Tagesquote im Zustand Level ≥ 3 > Basisrate, zirkulärer Shift-Test, einseitig.
- **T3:** Brier(v1.1) < Brier(M1 = logVIX mit E-Koeffizienten −5,2499 + 1,5579 · ln VIX), Block-Bootstrap, gepaart.
- Benjamini-Hochberg je Stichprobe über die drei Tests, q = 0,10.

**Entscheidung (strenger als im Protokoll):** „belegt" nur, wenn T1 und T2 auf H1 bestehen **und** auf dem blinden H2 die Tagesquote
im Zustand Level ≥ 3 über der H2-Basisrate liegt mit Shift-p < 0,10. Sonst bleibt das Modell im Schattenmodus.

**Offenlegung:** Für diesen Zähler kenne ich die H1-Tagesquoten bereits aus dem v1.0-Lauf (Level ≥ 3: 44,3 % gegen 22,1 % Basis; Level 4: 16,1 %).
H1 ist deshalb keine blinde Prüfung. Blind sind H2 komplett sowie T3 und alle p-Werte auf H1.

---

# 5. Ergebnis der Holdout-Läufe (22.11.2026, je ein Lauf)

Vor dem Lauf korrigiert: Im Trockenlauf auf E schätzte der Bootstrap die Referenz-Konstante je Ziehung neu.
Laut Protokoll ist sie die feste Basisrate der Stichprobe. Die Korrektur erfolgte, bevor H1 oder H2 gerechnet wurden.
Die H2-Zahlen wurden mit einer zweiten Spleiß-Methode (Niveau statt Renditekette) unabhängig nachgerechnet und sind identisch.

## Level als Zustand: Anteil der Tage mit ≥ 5 % Rückgang binnen 45 Sessions (Zahl der Tage)

| Zustand | H2 1999–2007 (blind) | E 2007–2016 (Entwicklung) | H1 2017–2026 (nicht blind) | Gesamt |
|---|---|---|---|---|
| Level 0 | 20,2 % (490) | 23,8 % (688) | 14,2 % (723) | 19,3 % (1 901) |
| Level 1 | 21,3 % (254) | 24,4 % (324) | 28,6 % (496) | 25,6 % (1 074) |
| Level 2 | 33,0 % (112) | 32,9 % (158) | 21,6 % (222) | 27,8 % (492) |
| Level 3 | 6,2 % (32) | 45,5 % (66) | 54,8 % (84) | 42,9 % (182) |
| Level 4 | 16,7 % (6) | 73,9 % (23) | 16,1 % (31) | 38,3 % (60) |
| **Warnzustand (≥ 3)** | **7,9 % (38)** | **52,8 % (89)** | **44,3 % (115)** | 41,7 % (242) |
| Alle Gate-Tage | 21,6 % (894) | 27,2 % (1 259) | 22,1 % (1 556) | 23,7 % (3 709) |

## Tests

| | H2 (blind) | E (in-sample) | H1 |
|---|---|---|---|
| T1 Brier Modell / Konstante | 0,1744 / 0,1693, p = 0,728 | 0,1924 / 0,1979, p = 0,246 | 0,1712 / 0,1722, p = 0,605 |
| T2 Warnzustand gegen Basisrate (Shift-p) | 0,899 | 0,019 | 0,009 |
| T3 Brier Modell / logVIX | 0,1744 / 0,1621, p = 0,953 | 0,1924 / 0,1954, p = 0,382 | 0,1712 / 0,1774, p = 0,241 |
| AUC Modell / logVIX | 0,526 / 0,647 | 0,571 / 0,596 | 0,613 / 0,521 |
| VIX-Benchmark gleicher Häufigkeit wie Warnzustand | 47,4 % | 19,1 % | 23,5 % |
| Erstsignal Level ≥ 3 | 2/10 | 5/15 | 5/20 |
| Mittlere 45-Sessions-Rendite Warnzustand / alle Gate-Tage | +2,0 % / +1,2 % | +0,2 % / +0,9 % | +1,9 % / +1,9 % |
| Median Vorlauf bis −5 % bei Treffern | 11 Sessions | 14 Sessions | 19 Sessions |

BH (q = 0,10) je Stichprobe: Auf H1 besteht nur T2, auf H2 besteht nichts.

## Entscheidung

**Nicht belegt.** T1 scheitert auf H1, und im blinden H2 liegt die Quote im Warnzustand unter der Basisrate (7,9 % gegen 21,6 %).
Das Modell bleibt im Schattenmodus. Es gibt keinen zweiten Versuch auf H1 oder H2.

## Lesart

- Als Erstsignal hat kein Level einen Vorsprung (v1.0-Ergebnis bestätigt).
- Als Zustand war Level ≥ 3 in 2007–2016 und 2017–2026 mit etwa doppelter Quote verbunden, in 1999–2007 mit einem Drittel der Basisrate.
  2017–2026 war dabei keine blinde Prüfung.
- Der Brier-Test scheitert schon in der Entwicklungsstichprobe (p = 0,25). Als Wahrscheinlichkeitsmodell ist das mit rund drei
  unabhängigen Korrekturen pro Jahr nicht von der Basisrate zu unterscheiden.
- Level 4 ist nicht gefährlicher als Level 3: 73,9 % → 16,1 % → 16,7 %.
- Das VIX-Niveau ist kein stabiler Ersatz: 2007–2026 nutzlos, 1999–2007 besser als das Modell.
- Aussteigen im Warnzustand hat 2017–2026 im Mittel nichts gebracht (45-Sessions-Rendite gleich der aller Gate-Tage; nur abgeschlossene Fenster,
  die Tage vom 28.09. bis 04.11.2026 fehlen darin noch).

## Komponenten je Ära (Lift = Quote bei aktiver Komponente / Basisrate, in Klammern Shift-p)

| Komponente | H2 1999–2007 | E 2007–2016 | H1 2017–2026 |
|---|---|---|---|
| C Credit | 1,38 (0,079) | 1,63 (0,001) | 1,15 (0,316) |
| B Breadth | 0,77 (0,668) | 1,70 (0,030) | 1,88 (0,021) |
| R Rotation | 0,90 (0,684) | 1,23 (0,211) | 1,13 (0,296) |
| V Volatility | 1,00 (0,505) | 1,06 (0,382) | 1,63 (0,001) |
| S Small Caps (verworfen) | 1,43 (0,187) | 1,31 (0,192) | 1,73 (0,013) |
| F Financials (verworfen) | 0,88 (0,782) | 0,84 (0,807) | 1,35 (0,015) |
| D Sektorbreite (verworfen) | 0,46 (0,932) | 1,08 (0,414) | 1,56 (0,098) |

Die Rangfolge kippt zwischen den Ären. Jede Gewichtung oder Auswahl nach einer Ära wäre in der nächsten falsch gewesen.

## Warnzustand in H2 (12 Läufe, 38 Tage)

03.02.2000 (Treffer, −6,9 %) · 24.09.–02.10.2003 (−1,1 %) · 18.11.2003 (−0,1 %) · 04.–05.02.2004 (−2,9 %) · 09.–31.03.2004 (−4,6 %) ·
07.–31.01.2005 (−2,1 %) · 12.04.2005 (−4,1 %) · 24.08.–04.10.2005 (−4,8 %) · 01.11.2005 (+1,0 %) · 16.05.2006 (Treffer, −5,2 %) ·
01.–02.06.2006 (Treffer, −5,0 %) · 22.–26.03.2007 (−1,1 %).
Drei Läufe endeten zwischen −4,1 % und −4,8 %, also knapp unter der festen 5-%-Schwelle. Das ändert das Ergebnis nicht, zeigt aber, wie stark es an der Schwelle hängt.

## Herbst 2026 (19 Tage im Warnzustand)

09., 10., 14., 15.09. [BRV]: nach Buchstabe kein Treffer (−5 % erst nach Session 45). 28.–29.09. [BRV] und 15.10.–04.11. [CRV]: 15 Treffer.

## Kandidaten fürs D-Regelwerk (verworfen)

1. Erstsignal Level 2/3/4 als Frühwarnung (v1.0): kein Vorsprung.
2. Zähler um Small Caps, Financials, Sektorbreite erweitern: in der Kreuzvalidierung schlechter.
3. Einzelgewichte je Komponente (logistisch): überangepasst, Lifts kippen zwischen Ären.
4. Datengetriebene Komponentenauswahl (Lift ≥ 1,25): instabil, schlechter als der feste Zähler.
5. 10-Tage-Glättung des Zählers: schlechter als der Rohwert.
6. VIX-Niveau und Abstand zum Hoch als Zusatzmerkmale: kein stabiler Beitrag.
7. Level 4 als höchste Warnstufe: nicht gefährlicher als Level 3.
8. v1.1 (Zustandslesart) als belegtes Modell: blinder Test nicht bestanden.

## Nur vorwärts prüfbar (nicht getestet, durch alle drei Stichproben gefärbt)

- H-CR4: Credit und Small Caps sind die einzigen Komponenten mit Lift > 1 in allen drei Ären.
- H-CR5: volatilitätsskalierte Zielgröße statt fester 5 %.
- Live-Test v1.1: Tage im Warnzustand nach dem 20.11.2026 (läuft im Tab mit).
