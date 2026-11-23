# Zwei Signale aus dem TSF-Rückblick: Prüfung über die Historie

Stand 22.11.2026. Skript: `research/tsf_post_signale.py`.

## 1. Vorab festgelegt (vor dem Lauf geschrieben, ein Lauf, kein Nachstellen)

Anlass: Der TSF-Rückblick vom November 2026 zeigt zwei Signale, die sich mit freien Daten rechnen lassen. Alex will sie im Indikator haben. Offen ist, ob sie ins Level zählen sollen.

Signal X, RSP überdehnt:

- Quelle: „Whenever it becomes 2x ATR extended from EMA 21 like now, it usually tops" (RSP, Tageschart).
- Regel: (Schluss − EMA 21 des Schlusskurses) / ATR 14 ≥ 2,0. ATR nach Wilder, RSP dividendenbereinigt. Die ATR-Länge nennt TSF nicht, 14 ist der übliche Standard.

Signal Q, Flucht aus High Beta:

- Quelle: SentimenTrader „S&P High Beta / S&P High Quality Relative Ratio Rank", von TSF als „complete crash in high beta vs high quality" gezeigt.
- Regel: Verhältnis SPHB/SPHQ, Rang = Lage im Bereich der letzten 84 Sessions in Prozent (SentimenTrader beschreibt den Rang als Lage im Bereich der letzten vier Monate). Signal, wenn der Rang heute ≤ 20 ist und in den letzten 10 Sessions ≥ 90 war. TSF nennt keine Schwellen, der gezeigte Fall endet bei 19,31. Die Schwellen sind meine Übersetzung von „straight line down".

Messung:

- Zielgröße wie im Modell: tiefster SPY-Schluss in t+1 bis t+45 mindestens 5 % unter dem Schluss t.
- Hauptlesart: Signaltage an Gate-Tagen (S&P 500) gegen alle Gate-Tage desselben Zeitraums, mit zirkulärem Shift-Test.
- Ereignis: erster Signaltag nach 20 Sessions ohne Signal.
- Zwei Zeithälften je Signal.
- Level-Frage: Level + X und Level + X + Q als neue Zählung. Entscheidend sind die Tage, die erst durch die neuen Bausteine auf 3 oder höher kommen.
- Nebenlesart: alle Tage ohne Gate.

Einordnung vorab: Der Zeitraum ist verbraucht (Entwicklung und beide Halteproben), die Signale sind im Nachhinein ausgewählt. Das Ergebnis ist beschreibend und kann einen Einbau ins Level nicht belegen. Es kann aber zeigen, dass ein Signal schon rückblickend nichts trägt.

Entscheidungsregel, vorab: Ein Signal kommt nur dann als Kandidat für das Level in Frage, wenn die hinzugekommenen Tage (neue Zählung ≥ 3, altes Level < 3) eine Quote über der Basis haben und beide Zeithälften in dieselbe Richtung zeigen. Sonst bleibt es eine Anzeige neben dem Level.

## 2. Ergebnis (ein Lauf, 22.11.2026)

Die Regeln treffen die Fälle, die TSF zeigt: X feuerte am 22.10., 29.10. und 04.11.2026, Q am 16.10.2026 (Rang 18,8, TSF zeigt 19,31).

Signal X, RSP überdehnt, ab 30.05.2003:

| Lesart | Signal | Basis |
|---|---|---|
| Gate-Tage | 19,5 % (163 von 836) | 21,9 % (793 von 3 629) |
| Shift-Test | p = 0,80 | |
| Ereignis (erster Tag nach 20 Sessions) | 24,6 % (16 von 65), 2,8 pro Jahr | 21,9 % |
| Hälfte bis 02/2015 | 20,2 % | 21,6 % |
| Hälfte ab 02/2015 | 18,6 % | 22,1 % |
| alle Tage ohne Gate | 20,1 % | 26,3 % |

- X ist an 23 % aller Gate-Tage aktiv und liegt in beiden Hälften unter der Basis. Es zeigt Stärke an, kein Korrekturrisiko für den S&P 500.
- Level + X: Der Warnzustand fällt von 41,1 % (101 von 246) auf 39,1 % (104 von 266). Die 20 hinzugekommenen Tage haben 15,0 % (3 von 20), in der zweiten Hälfte 0 von 11.
- TSFs Aussage bezieht sich auf ein Hoch in RSP selbst. Das habe ich nicht gemessen, die Zielgröße des Modells ist die Korrektur im S&P 500.

Signal Q, Flucht aus High Beta, ab 15.09.2011:

- 8 Signaltage in 15 Jahren, das sind zwei Ereignisse: 27.01. bis 04.02.2025 und 16.10.2026. Auf beide folgte eine Korrektur von mindestens 5 % (8 von 8 Tagen, 2 von 2 Ereignissen, Basis 21,1 %).
- Der Shift-Test gibt p = 0,013. Bei zwei Ereignissen trägt das nichts, und eines davon ist der Fall, wegen dem TSF das Signal gezeigt hat.
- In der ersten Hälfte (bis 04/2019) gab es kein Signal.
- Level + Q: Kein einziger Tag kommt neu in den Warnzustand. Am 16.10.2026 stand das Level schon auf 3.
- TSF markiert im Chart seit 2020 rund neun Phasen. Meine Regel (Sturz innerhalb von 10 Sessions) ist also enger als TSFs Lesart. Eine lockerere Regel wäre ein zweiter Versuch und unterbleibt.

Level + X + Q, ab 15.09.2011: Warnzustand 45,0 % (89 von 198) gegen 41,8 % (89 von 213) mit beiden Bausteinen. Die 15 hinzugekommenen Tage haben 0 Treffer.

## 3. Entscheidung nach der Regel aus Abschnitt 1

- X kommt nicht ins Level. Die hinzugekommenen Tage liegen unter der Basis, die zweite Hälfte hat keinen Treffer, und der Warnzustand wird schlechter.
- Q kommt nicht ins Level. Es gibt keine hinzugekommenen Tage, an denen sich die Regel prüfen ließe, und zwei Ereignisse reichen für nichts.
- Als Anzeige neben dem Level taugt X nicht, weil es als Warnung gelesen würde und keine ist. Q wäre als seltener Hinweis möglich, mit dem Vermerk „2 Fälle seit 2011".

Beides ändert nichts daran, was dem Eigenbau gegenüber TSF fehlt: der Auslöser (siehe `LEVEL_VERGLEICH_TSF.md`, Abschnitt 5).
