# Correction-Risk-Modell – Forschungsprotokoll v1.1

Fixiert am 22.11.2026, **bevor** eine neue Zahl gerechnet wurde. Geprüft wurde vorab nur die Verfügbarkeit der Symbole.
Auftrag: v1.0 vollständig nachtesten und verbessern, ohne die Verbesserung an denselben Daten zu „beweisen", an denen sie gefunden wurde.

## 1. Stichproben

| Kürzel | Zweck | Signaltage |
|---|---|---|
| E | Entwicklung (Auswahl, Schätzung) | 20.06.2007 bis letzter Tag, dessen 45-Sessions-Fenster am 30.12.2016 endet |
| H1 | Holdout 1 | 03.01.2017 bis 20.11.2026 |
| H2 | Holdout 2, Proxy-Ära | erster gültiger Tag (März 1999) bis letzter Tag, dessen Fenster am 19.06.2007 endet |

H2 nutzt verkettete Renditereihen: HYG←VWEHX, IEF←VFITX, RSP←VADAX, IWM←^RUT (vor Auflage des ETF die Rendite des Proxys).

**Offenlegung:** Aus dem v1.0-Lauf kenne ich für beide Hälften bereits Episoden- und Tagesquoten der Zähl-Level
(z. B. Tagesquote Level ≥ 3: 50,5 % bis 2016, 44,3 % ab 2017). H1 ist für Tests gegen die Basisrate deshalb nicht blind.
Blind sind: alles zu neuen Komponenten, alles zum VIX-Niveau, der Vergleich gegen den VIX-Benchmark (T3) und die gesamte Ära H2.

## 2. Unverändert aus v1.0

Gate (SPY ≤ 3 % unter 252-Tage-Schlusshoch), Zielgröße Y45 (≥ 5 % unter Signalschluss binnen 45 Sessions), Zensierung, Episodenregel (20 Sessions).

## 3. Komponenten-Bibliothek (7)

Einheitliche Form wie v1.0: Reihe auf der Risk-off-Seite ihres SMA50 und 20-Tage-Veränderung in Risk-off-Richtung. Keine Parametervarianten.

| Kürzel | Markt | Regel |
|---|---|---|
| C | Credit | HYG/IEF fällt |
| B | Breadth | RSP fällt |
| R | Rotation | XLY/XLP fällt |
| V | Volatility | VIX steigt |
| S | Small Caps (neu) | IWM fällt |
| F | Financials (neu) | XLF/SPY fällt |
| D | Sektorbreite (neu) | mindestens 5 von 9 Sektor-SPDRs unter ihrem SMA50 |

Verworfen vor jeder Rechnung: MOVE (Historie erst ab 11/2002, mit Lücken; Regel war: nur aufnehmen, wenn vor 06/1999 verfügbar).
Bewusst nicht aufgenommen: Anleihen-Richtung (Vorzeichen regimeabhängig), VIX-Terminstruktur (Dublette zu V).

## 4. Merkmale

`logVIX` (Niveau), `dist_high` (Abstand zum 252-Tage-Hoch), `n4` = C+B+R+V, `n7` = alle sieben,
`n4s`/`n7s` = 10-Sessions-Mittel der Zählung, `nSel` = Zählung der Komponenten, die in den Trainingsdaten
Lift ≥ 1,25 bei mindestens 50 wahren Gate-Tagen haben.

## 5. Kandidaten (logistische Regression auf Gate-Tagen von E)

| Modell | Merkmale |
|---|---|
| M1 | logVIX |
| M2 | logVIX + dist_high |
| M3 | logVIX + n4 |
| M4 | logVIX + n7 |
| M5 | logVIX + n4s |
| M6 | logVIX + n7s |
| M7 | logVIX + nSel |
| M8 | logVIX + dist_high + n7 |

Referenzen ohne Auswahlrecht: M0 (Konstante), v1.0 (Zähl-Level aus n4).

## 6. Auswahl (nur auf E)

- Leave-one-year-out über die Kalenderjahre von E; Testjahre mit weniger als 20 Gate-Tagen entfallen als Fold. 45 Sessions vor und nach dem Testjahr werden aus dem Training entfernt.
- Maß: mittlerer Log-Loss je Fold. Bestes Modell = kleinster Mittelwert.
- Gepaarte 1-SE-Regel: Ein Modell gilt als gleichwertig, wenn seine mittlere Fold-Differenz zum besten höchstens 1 Standardfehler dieser Differenzen beträgt.
  Gewählt wird das gleichwertige Modell mit den wenigsten Merkmalen, bei Gleichstand das mit dem kleineren Log-Loss.
- Bei M7 läuft die Komponentenauswahl innerhalb jedes Folds.

## 7. Einfrieren

Koeffizienten aus allen Gate-Tagen von E. Level 0–4 über feste Wahrscheinlichkeitsgrenzen: die 50-, 75-, 90- und 97-%-Quantile
der geschätzten Wahrscheinlichkeit an den Gate-Tagen von E. Danach keine Änderung mehr.

## 8. Tests auf H1 (ein Lauf)

- **T1:** Brier(Modell) < Brier(Konstante = Basisrate derselben Stichprobe). Moving-Block-Bootstrap über die Gate-Tage, Blocklänge 60, 5 000 Wiederholungen, Seed 20261122, einseitig.
- **T2:** Tagesquote an Level ≥ 3 > Basisrate der Gate-Tage. Zirkulärer Shift-Test über die Gate-Tag-Folge (alle Versätze 60 … N−60), einseitig.
- **T3** (nur wenn das gewählte Modell mehr als logVIX enthält): Brier(Modell) < Brier(M1, auf E geschätzt). Gleicher Bootstrap, gepaart.
- Benjamini-Hochberg über die anwendbaren Tests, q = 0,10.

**Entscheidung:** „belegt", wenn T1 und T2 bestehen. T3 entscheidet, ob der Cross-Market-Teil über das VIX-Niveau hinaus etwas beiträgt.
Kein zweiter Versuch auf H1: Fällt das Modell durch, wird es als verworfen dokumentiert.

## 9. Beschreibend (ohne Entscheidungsgewicht)

AUC, Kalibrierung je Level, Episodenstarts Level ≥ 3, Vorwärtsrendite über 45 Sessions an Level-≥-3-Tagen gegen alle Gate-Tage,
alles zusätzlich auf H2. Volltest v1.0: jede Komponente einzeln, Zähl-Level als Zustand (Tagesquote mit Shift-Test) und als Erstsignal,
dazu ein VIX-Benchmark gleicher Häufigkeit (die Gate-Tage mit dem höchsten VIX, so viele wie Level-≥-3-Tage).
