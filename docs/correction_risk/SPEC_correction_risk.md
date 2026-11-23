# Correction-Risk-Modell (Eigenbau) – Spec v1.0

Fixiert am 22.11.2026, **vor** dem ersten Backtest-Lauf. Kein Parameter wurde an Daten angepasst.
Vorbild ist die Struktur des TSF Correction Risk Model (Gate nahe Hoch, Bestätigungen aus
anderen Märkten, Level-Leiter). Die TSF-Inputs sind nicht bekannt, das hier ist ein eigenes Modell.

## 1. Daten

- Quelle: Yahoo Finance, Tagesschlusskurse, dividendenbereinigt (`auto_adjust=True`).
- Symbole: SPY, RSP, HYG, IEF, XLY, XLP, ^VIX.
- Auswertung ab dem ersten Tag, an dem alle Komponenten definiert sind (HYG startet April 2007).

## 2. Gate

`G`: SPY-Schluss ≥ 97 % des höchsten Schlusskurses der letzten 252 Sessions (inkl. heute).
Außerhalb des Gates gibt das Modell kein Level aus (Level 0, Status „außerhalb Gate").

## 3. Komponenten (je wahr/falsch, nur Daten bis Schluss t)

Einheitliche Form: Reihe liegt auf der Risk-off-Seite ihres 50-Tage-SMA **und** ihre 20-Tage-Veränderung zeigt in Risk-off-Richtung.

| Kürzel | Markt | Reihe x | Bedingung |
|---|---|---|---|
| C | Credit | HYG / IEF | x < SMA50(x) und x[t]/x[t−20] < 1 |
| B | Breadth | RSP | x < SMA50(x) und x[t]/x[t−20] < 1 |
| R | Rotation | XLY / XLP | x < SMA50(x) und x[t]/x[t−20] < 1 |
| V | Volatility | ^VIX | x > SMA50(x) und x[t]/x[t−20] > 1 |

Begründung B absolut statt RSP/SPY: Die Ratio fällt in engen Bullenmärkten jahrelang und wäre fast immer wahr.
Mit dem Gate zusammen ist „RSP unter SMA50" bereits eine Divergenz (SPY nahe Hoch, gleichgewichteter Index im Abwärtsdrift).

## 4. Level

`Level = G ? (C + B + R + V) : 0`, also 0 bis 4.

## 5. Zielgrößen

- Primär `Y45`: tiefster SPY-Schluss in t+1 … t+45 liegt ≥ 5 % unter Schluss t.
- Sekundär (nur beschreibend): `Y10` = ≥ 3 % in 10 Sessions; schlechtester Dip über 45 Sessions.
- Unvollständige Fenster am Datenende: Treffer zählt, sobald erreicht; sonst wird der Tag ausgeschlossen.

## 6. Baseline

Anteil `Y45 = 1` über alle Gate-Tage desselben Zeitraums („zufälliger Tag nahe Hoch").

## 7. Episoden

Für Schwelle k ∈ {1,2,3,4}: Tag t ist Episodenstart, wenn Level[t] ≥ k und max(Level[t−20 … t−1]) < k.
Ausgewertet werden Episodenstarts, nicht Einzeltage.

## 8. Tests (primär)

- Drei Hypothesen: Trefferquote der Episodenstarts für k = 2, 3, 4 liegt über der Baseline.
- Placebo-Test: 10 000 Ziehungen von je n zufälligen Gate-Tagen mit Mindestabstand 20 Sessions (n = Zahl der Episoden).
  p = Anteil der Ziehungen mit Trefferquote ≥ beobachtet. Seed 20261122.
- Benjamini-Hochberg über die drei p-Werte, q = 0,10.
- Zeitraum: gesamte Stichprobe. Beschreibend zusätzlich: Hälften bis 31.12.2016 / ab 01.01.2017 und 2012 bis heute (TSF-Vergleich).

## 9. Entscheidungsregel

Ein Level gilt als **belegt**, wenn es BH-signifikant ist **und** die Trefferquote in beiden Hälften über der jeweiligen Baseline liegt.
Alles andere läuft als **nicht belegt** im Schattenmodus (Anzeige ja, keine Handlungsautorität).

## 10. Bekannte Schwächen vorab

- Die Komponentenwahl ist durch Wissen über 2007–2026 gefärbt (HY-Schwäche vor 2022 usw.). Echtes Out-of-Sample beginnt heute.
- Episoden mit 20 Sessions Abstand haben überlappende 45-Tage-Fenster. Der Placebo-Test bildet das nach, hebt es aber nicht auf.
- Kleine n bei Level 3 und 4 sind zu erwarten.

---

# Ergebnis des einen Laufs (22.11.2026, Daten bis Schluss 20.11.2026)

Auswertung 20.06.2007 bis 20.11.2026, 4 888 Handelstage, 2 856 Gate-Tage mit bekanntem Ausgang.
Zahlen mit einer zweiten, unabhängigen Implementierung nachgerechnet (identisch).

| Schwelle | Episoden | Treffer | Quote | Baseline | p (Placebo) | BH (q = 0,10) | bis 2016 | ab 2017 | Status |
|---|---|---|---|---|---|---|---|---|---|
| Level ≥ 1 | 36 | 10 | 27,8 % | 24,0 % | – | – | 6/18 | 4/18 | nicht getestet |
| Level ≥ 2 | 45 | 11 | 24,4 % | 24,0 % | 0,605 | nein | 6/19 | 5/26 | nicht belegt |
| Level ≥ 3 | 35 | 10 | 28,6 % | 24,0 % | 0,334 | nein | 5/15 | 5/20 | nicht belegt |
| Level ≥ 4 | 15 | 7 | 46,7 % | 24,0 % | 0,039 | nein (Grenze 0,033) | 5/7 | 2/8 | nicht belegt |

Baselines der Hälften: 26,3 % (bis 2016), 22,1 % (ab 2017).

## Lesart

- Level 2 und 3 sind beim Episodenstart nicht von einem zufälligen Tag nahe Hoch zu unterscheiden.
- Level 4 (alle vier Märkte) liegt bei 7 von 15 gegen 24 % Baseline. Der rohe p-Wert von 0,039 übersteht die BH-Korrektur nicht,
  und der Effekt kommt fast ganz aus 2007–2016 (5/7), ab 2017 sind es 2/8 gegen 22 % Baseline.
- Nach Entscheidungsregel (Abschnitt 9) ist kein Level belegt. Das Modell läuft im Schattenmodus.

## Abgleich der Zielgröße mit TSF (2012 bis heute)

| Kennzahl | hier | TSF-Sheet |
|---|---|---|
| ≥ 5 % binnen 45 Sessions, Tag nahe Hoch | 21,1 % | 20 % |
| ≥ 3 % binnen 10 Sessions, Tag nahe Hoch | 12,5 % | 12 % |
| Median schlechtester Dip, 45 Sessions | −2,1 % | −2,1 % |

Die Zielgröße ist also vergleichbar definiert. Die TSF-Trefferquoten (Level 3: 38–57 %, Level 4: 67–82 %) erreicht dieses Modell nicht.

## Das Top vom Herbst 2026

- Level 3 [BRV] am 09.09. (Episodenstart), erneut am 14.09. und 28.09., Level 3 [CRV] am 15.10. und 04.11. Level 4 wurde nie erreicht.
- Nach Buchstabe der Spec ist die Episode vom 09.09. ein Fehlsignal: Tief im 45-Sessions-Fenster 733,00 am 05.11. (−3,6 % zum Signalschluss 760,51),
  die −5 % kamen erst in Session 51 am 19.11. Vom Schlusshoch 779,09 (06.10.) bis 689,81 (20.11.) sind es −11,5 %.

## Beobachtungen nach dem Lauf (nicht getestet, vor einem Test neu zu registrieren)

- H-CR2 Persistenz: Auf Tagesebene liegt die Quote an Level-≥-3-Tagen bei 47 % (208 Tage), beim Episodenstart nur bei 29 %.
  Die Tage sind stark autokorreliert, das ist kein Beleg. Hypothese für v1.1: Level ≥ 3 an mindestens 5 der letzten 10 Sessions.
- H-CR3 Zielgröße vom Hoch statt vom Signalschluss (≥ 5 % unter dem höchsten Schluss im Fenster). Würde Fälle wie September 2026 anders zählen.
- Kandidaten fürs D-Regelwerk: „Erstberührung Level 2/3 aus vier Cross-Market-Bestätigungen (SMA50 + 20-Tage-Richtung) hat keinen Edge auf ≥ 5 %/45 Sessions."
