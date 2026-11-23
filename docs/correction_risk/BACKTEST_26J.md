# Großer Backtest 2000–2026 – Festlegung vor dem Lauf

Geschrieben am 22.11.2026, bevor eine Zahl dieses Laufs gerechnet wurde. Das Modell ist das eingefrorene v1.1
(Signale unverändert seit v1.0, Warnzustand = Gate an und mindestens 3 von 4 Bestätigungen). Hier wird nichts angepasst oder ausgewählt.

**Einordnung:** Der Zeitraum enthält die Entwicklungsjahre 2007–2016. Der Lauf ist beschreibend und kein neuer Test des Modells.
Alle vorab festgelegten Varianten werden berichtet, auch die schlechten.

## Zeitraum und Daten

- 03.01.2000 bis 20.11.2026, Tagesschlusskurse von Yahoo Finance, dividendenbereinigt.
- Vor Auflage der ETFs verkettete Renditereihen wie in v1.1: HYG←VWEHX, IEF←VFITX, RSP←VADAX.
- Kasse: 13-Wochen-T-Bill (^IRX), Tageszins = Vortageswert / 252.

## Teil 1: Quoten

Wie in v1.1: Anteil der Gate-Tage je Level und im Warnzustand, denen binnen 45 Sessions ein SPY-Schluss ≥ 5 % unter dem Tagesschluss folgt.
Zusätzlich je Kalenderjahr und als Nebenbefund dieselbe Rechnung mit QQQ als Ziel (≥ 5 % und ≥ 8 %).

## Teil 2: Alle Korrekturen ab Hoch

- **Hoch:** Tag T mit neuem 252-Tage-Schlusshoch.
- **Korrektur:** SPY schließt ≥ 5 % unter dem Schluss von T, bevor ein neues 252-Tage-Schlusshoch entsteht. Tag F = erster solcher Schluss.
  Tiefe = tiefster Schluss bis zum nächsten 252-Tage-Schlusshoch.
- **Gewarnt:** mindestens ein Tag im Warnzustand zwischen 20 Sessions vor T und dem Tag vor F. Vorlauf = Sessions vom ersten solchen Tag bis F.
  Dieselbe Zählung für „mindestens 2 Bestätigungen".
- **Zufallsvergleich:** Die Warnzustand-Reihe wird zirkulär gegen die Kurse verschoben (alle Versätze 60 … N−60).
  Berichtet werden die mittlere Erkennungsquote der Verschiebungen und der Anteil, der mindestens die beobachtete Quote erreicht.

## Teil 3: Ausstieg im Warnzustand

Signal zum Schluss von Tag t, Umsetzung zum Schluss von t+1 (Hauptfall, ein Tag Verzögerung). Nebenrechnung: Umsetzung zum Schluss von t.
Keine Kosten, keine Steuern.

| Kürzel | Regel |
|---|---|
| B0 | Buy and Hold SPY |
| O1 | Kasse, solange der Warnzustand anliegt |
| O2 | Kasse ab einem Warnzustand-Tag bis 45 Sessions nach dem letzten |
| O3 | wie O2, aber nur halbe Position |
| B1 | Vergleich: SPY nur über der 200-Tage-Linie, sonst Kasse |

Kennzahlen: Rendite p. a., Volatilität, Sharpe (über Kasse), größter Rückgang, Anteil der Zeit investiert, Zahl der Ausstiege.
Für O1 und O2 Zufallsvergleich wie in Teil 2: Kassen-Tage zirkulär verschoben, Anteil der Verschiebungen mit mindestens so hoher Rendite
und Anteil mit mindestens so kleinem größtem Rückgang. Zusätzlich O2 gegen B0 je Teilzeitraum (2000–2007, 2007–2016, 2017–2026).

## Teil 4: Liste

Alle Läufe im Warnzustand (Tage mit höchstens 10 Sessions Abstand zusammengefasst) mit Dauer, höchstem Level,
schlechtestem Dip und Rendite über 45 Sessions ab dem ersten Tag.

---

# Ergebnis (Lauf vom 22.11.2026, Daten bis Schluss 20.11.2026)

Zeitraum: 6763 Handelstage, 26,9 Jahre. Gate an 54,6 % der Tage. Bericht mit Charts und allen Listen: https://claude.ai/artifact/XohJuyQNxirkwhVQMQYPMX

## Teil 1: Quoten

| Zustand | Tage | Quote |
|---|---|---|
| Level 0 | 1890 | 18,6 % |
| Level 1 | 1057 | 24,8 % |
| Level 2 | 496 | 27,8 % |
| Level 3 | 187 | 42,2 % |
| Level 4 | 60 | 38,3 % |
| **Warnzustand (≥ 3)** | 247 | **41,3 %** |
| Alle Tage nahe Hoch | 3690 | 23,1 % |

Shift-Test: Warnzustand p = 0,004, mindestens 2 Bestätigungen 32,3 % an 743 Tagen, p = 0,007. Erstsignal Level ≥ 3: 13 von 46.

| Jahr | Tage nahe Hoch | Basisrate | Tage im Warnzustand | davon Treffer |
|---|---|---|---|---|
| 2000 | 61 | 98,4 % | 1 | 1 |
| 2003 | 131 | 0,0 % | 4 | 0 |
| 2004 | 165 | 21,8 % | 6 | 0 |
| 2005 | 184 | 10,3 % | 21 | 0 |
| 2006 | 194 | 12,9 % | 3 | 2 |
| 2007 | 153 | 52,9 % | 13 | 10 |
| 2009 | 56 | 19,6 % | 0 | 0 |
| 2010 | 109 | 42,2 % | 0 | 0 |
| 2011 | 107 | 38,3 % | 1 | 0 |
| 2012 | 151 | 40,4 % | 5 | 5 |
| 2013 | 229 | 3,5 % | 9 | 0 |
| 2014 | 220 | 20,0 % | 24 | 9 |
| 2015 | 180 | 40,0 % | 30 | 24 |
| 2016 | 194 | 2,6 % | 15 | 0 |
| 2017 | 251 | 0,0 % | 27 | 0 |
| 2018 | 100 | 57,0 % | 2 | 2 |
| 2019 | 160 | 21,9 % | 11 | 0 |
| 2020 | 107 | 45,8 % | 5 | 5 |
| 2021 | 230 | 13,0 % | 14 | 8 |
| 2022 | 10 | 100,0 % | 0 | 0 |
| 2023 | 116 | 26,7 % | 1 | 0 |
| 2024 | 220 | 12,3 % | 4 | 0 |
| 2025 | 176 | 18,8 % | 14 | 3 |
| 2026 | 186 | 38,7 % | 37 | 33 |

Nebenbefund QQQ als Ziel: ≥ 5 % binnen 45 Sessions 47,8 % im Warnzustand gegen 33,7 %, ≥ 8 % 30,6 % gegen 17,8 %, Median schlechtester Dip −4,8 % gegen −3,1 %.

## Teil 2: Alle Korrekturen ab Hoch

37 Rückgänge ≥ 5 % ab einem 252-Tage-Hoch, davon 11 ab 10 %.

| | erkannt | Zufall über alle Tage (vorab festgelegt) | Zufall nur nahe Hoch (Nachtrag) |
|---|---|---|---|
| Warnzustand | 22 von 37 | Mittel 11,0, p = 0,0002 | Mittel 16,5 (13–20), p = 0,019 |
| ≥ 2 Bestätigungen | 31 von 37 | Mittel 18,8, p = 0,0002 | Mittel 27,6 (24–31), p = 0,093 |

Rückgänge ab 10 %: 8 von 11 mit Warnzustand vorher. Ohne Warnung: 24.03.2000 (−47,5 %), 23.04.2010 (−15,7 %), 26.01.2018 (−10,1 %).
Median Vorlauf bis −5 %: 21,5 Sessions, mindestens 10 Sessions in 15 von 22 Fällen. Schon bis zum Tag des Hochs lag der Warnzustand in 9 von 37 Fällen an.

**Zum Zufallsvergleich:** Die vorab festgelegte Verschiebung über alle Tage ist zu milde. Warnungen können nur nahe Hoch entstehen, und Korrekturen ab Hoch beginnen dort per Definition. Der Nachtrag verschiebt nur innerhalb der Tage nahe Hoch und ist der faire Maßstab.

## Teil 3: Ausstieg im Warnzustand

| Regel | Rendite p. a. | Volatilität | Sharpe | Größter Rückgang | Investiert | Ausstiege |
|---|---|---|---|---|---|---|
| B0 Buy and Hold | 7,79 % | 19,3 % | 0,39 | −55,2 % | 100,0 % | 0 |
| O1 Kasse im Warnzustand | 8,84 % | 19,1 % | 0,44 | −55,0 % | 96,3 % | 118 |
| O2 45 Sessions Kasse | 4,90 % | 16,4 % | 0,26 | −59,8 % | 65,2 % | 34 |
| O3 45 Sessions halbe Position | 6,47 % | 17,1 % | 0,34 | −54,1 % | 82,6 % | 34 |
| B1 200-Tage-Linie | 7,13 % | 11,6 % | 0,49 | −22,0 % | 74,5 % | 92 |
| O1 ohne Verzögerung | 8,46 % | 19,0 % | 0,42 | −53,9 % | 96,3 % | 118 |
| O2 ohne Verzögerung | 5,25 % | 16,3 % | 0,28 | −57,2 % | 65,2 % | 34 |

Zufallsvergleich (Kassentage verschoben, alle Tage): O1 Mittel 7,58 %, p = 0,043; größter Rückgang p = 0,49. O2 Mittel 5,74 %, p = 0,72; größter Rückgang im Mittel −47,3 %, p = 0,96. Nachtrag O1 nur nahe Hoch: Mittel 7,67 %, p = 0,003.

| Teilzeitraum | B0 | O1 | O2 | B1 |
|---|---|---|---|---|
| 2000–2007 | 2,18 % / −47,5 % | 3,15 % / −47,5 % | −2,49 % / −47,6 % | 6,42 % / −13,3 % |
| 2007–2016 | 6,24 % / −55,2 % | 7,39 % / −55,0 % | 2,85 % / −53,1 % | 4,65 % / −22,0 % |
| 2017–2026 | 13,82 % / −33,7 % | 14,83 % / −33,7 % | 12,99 % / −22,1 % | 10,15 % / −21,9 % |

(Rendite p. a. / größter Rückgang)

### Woher der O1-Vorsprung kommt (Nachtrag, nach dem Lauf gerechnet)

- 247 Kassentage. Mittlere SPY-Tagesrendite an diesen Tagen −0,094 %, an allen Tagen 0,037 %. Median 0,004 %, Anteil negativer Tage 49,8 %. Der Effekt sitzt im linken Rand, nicht im typischen Tag.
- Größte vermiedene Verlusttage: 10.10.2018 (−3,2 %), 21.08.2015 (−3,0 %), 05.08.2019 (−3,0 %), 13.05.2019 (−2,5 %), 26.07.2007 (−2,4 %), 03.02.2014 (−2,3 %).
- Ohne die fünf größten: 8,26 % p. a. O1 war in 11 Jahren besser und in 10 schlechter als Buy and Hold.
- Rendite p. a. nach Verzögerung in Tagen: 0: 8,46 %, 1: 8,84 %, 2: 7,65 %, 3: 8,00 %, 4: 7,04 %, 5: 7,80 %. Hauptfall ist 1.

## Teil 4: Läufe

54 Läufe im Warnzustand, am ersten Tag Treffer in 14 von 54. Die Liste steht im Bericht.

## Lesart

- Über 27 Jahre war die Quote im Warnzustand knapp doppelt so hoch wie die Basisrate. Die Treffer klumpen in wenigen Jahren (2007, 2014/15, 2021, 2026), und der Zeitraum enthält die Entwicklungsjahre.
- Die Erkennungsquote sieht besser aus, als sie ist: Mit mindestens 2 Bestätigungen werden 31 von 37 Korrekturen „erkannt“, ein Zufallssignal nahe Hoch schafft 27,6.
- Der Warnzustand ist selten ein Frühwarner. In 9 von 37 Fällen lag er schon am Hoch an, sonst kam er im beginnenden Rückgang.
- Langes Aussteigen (45 Sessions) kostet Rendite und schützt nicht. Im Bärenmarkt ist das Modell blind, weil es nur nahe Hoch misst.
- Kasse nur an Warnzustand-Tagen war besser als Buy and Hold, hängt aber an wenigen großen Verlusttagen und verschwindet bei zwei Tagen Verzögerung. Das ist eine Hypothese für den Live-Test, keine Regel.
