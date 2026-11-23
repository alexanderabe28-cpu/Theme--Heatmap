# R-/W-Baustein „Correction Risk (CR)" · v1.0

Stand 23.11.2026. Für die Project-Instructions „Daily & Weekly". Gilt für den manuellen R (morgens als Review) und das W.
Werkzeug: `cr_block.py` im App-Repo `Desktop\Theme--Heatmap` (Modul `correction_risk.py`, Spec v1.1, eingefroren 20.11.2026, Schattenmodus). Regeln und Testergebnisse: `docs\correction_risk\` im selben Repo. Nur S&P 500; die NASDAQ-Variante gibt es nur im Pine-Indikator und sie ist schwächer.

## Voraussetzung

Der Rechner ist mit der Sitzung verbunden und der Ordner `Theme--Heatmap` ist freigegeben (Shell: `mnt/Theme--Heatmap`). Ohne verbundenen Rechner: Zeile „CR n/a: Rechner nicht verbunden". Nichts schätzen, keine Werte aus TradingView abschreiben, keinen alten Block wiederverwenden.

## Ablauf im R

1. In der Shell des verbundenen Rechners ausführen (Timeout 90 s):
   `cd mnt/Theme--Heatmap && python cr_block.py; echo "EXIT=$?"`
2. `mnt/Theme--Heatmap/out/cr_latest.md` lesen.
3. In den R einfügen: Abschnitt von `### Correction Risk (CR)` bis vor `### Correction Risk · W-Block`, unverändert, als eigener Block direkt nach dem CT-Block.
4. EXIT 1: Die Datei trägt die Zeile „Datenstand" (Kerze älter als 4 Kalendertage), mitnehmen. EXIT 2: Block ersetzen durch „CR n/a" plus Fehlermeldung im Wortlaut.

## Lesart (Schattenmodus)

- Gate: SPY-Schluss ≥ 97 % des 252-Tage-Schlusshochs. Nur an Gate-Tagen gibt es ein Level.
- Buchstaben = aktive Bestätigungen: C Credit (HYG/IEF), B Breadth (RSP), R Rotation (XLY/XLP), V Volatilität (VIX). Aktiv heißt: Reihe auf der Risk-off-Seite ihrer SMA50 und 20-Tage-Veränderung in dieselbe Richtung.
- Level = Zahl der Bestätigungen an Gate-Tagen: 1 ELEVATED, 2 HIGH, 3 VERY HIGH, 4 EXTREME. Warnzustand ab 3. Die eigenen Zahlen tragen keine vier Stufen: im Holdout 2017–2026 folgte Level 3 an 55 % der Tage ein Rückgang ≥ 5 % binnen 45 Sessions, Level 4 nur an 16 %, Basis 22 %. Im blinden Test 1999–2007 lag der Warnzustand bei 8 %. Deshalb: kein Level wird gehandelt.
- Marker = erster Tag, an dem das Level höher ist als an den 20 Sessions davor (Erstsignal, wie die TSF-Dreiecke).
- Risikofenster „Tag n von 45" = Sessions seit dem letzten Warntag. Kein Ausstiegssignal: Kasse im Fenster hat im 26-Jahre-Lauf Rendite gekostet (Regel O2).
- „Kein Level (Gate aus)" mit 4 von 4 Bestätigungen heißt: der Index ist schon in der Korrektur. Das Modell warnt nur nahe am Hoch.
- Entry-Seite: Warnzustand im Führungs-Nachweis als „CR-Warnung (Schatten)" vermerken. Keine Sperre, keine Positionsgrößenänderung.
- Jeder neue Marker ab Level 3 und jeder erste Warntag nach geschlossenem Fenster bekommt im Tages-Zeugnis eine Zeile mit Bewertung nach 45 Sessions (Treffer: Schluss ≥ 5 % tiefer / Fehlalarm). Das ist der Live-Test seit 20.11.2026.

## W (samstags)

- Zusätzlich den `### Correction Risk · W-Block` übernehmen (Level je Tag, neue Marker, Warntage der Woche).
- Die Zeile „Live-Test" fortschreiben. Offene Warntage, deren 45 Sessions abgelaufen sind, mit Ergebnis ins Tages-Zeugnis.
- TSF-Signale (Posts von The Setup Factory) nur notieren, nicht ins Level übernehmen. Zusatzsignale wurden geprüft und abgelehnt (`docs\correction_risk\TSF_POST_SIGNALE.md`: RSP 2 ATR, SPHB/SPHQ).
- Wiedervorlage der Spec frühestens nach 20 Warntagen im Live-Test. Beförderung Schatten → live nur per W-Beschluss mit vorab festgelegtem Kriterium.

## Änderungen

Parameter und Schwellen nur in `correction_risk.py` mit Versionssprung (Spec v1.2) und neuem Einfrieren, nie im Block oder in `out/`. Nach jeder Änderung: `python -m pytest -q test_correction_risk.py` muss grün sein.
