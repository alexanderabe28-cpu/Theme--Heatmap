"""Baut die Datendateien fuer den Bericht aus results_26y.json. Aufruf: python make_data.py <datenordner> <zielordner>
Jede Datei ist {rows, meta}; meta traegt den Code, mit dem die Zahlen gerechnet wurden."""
import json, sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
res = json.loads((src / "results_26y.json").read_text())
R = Path("/home/claude/tsf/research")
code_main = (R / "backtest_26y.py").read_text()
code_check = (R / "backtest_26y_check.py").read_text()
code_self = Path(__file__).read_text()
EINGABE = ("Yahoo Finance, dividendenbereinigte Tagesschlusskurse bis 20.11.2026: SPY, RSP, HYG, IEF, XLY, XLP, ^VIX, QQQ, ^IRX; "
           "vor ETF-Auflage verkettet mit VWEHX, VFITX, VADAX. Modell: correction_risk.py Spec v1.1 (eingefroren).")


def meta(*codes):
    m = [{"label": n, "value": c, "type": "code", "lang": "python"} for n, c in codes]
    return m + [{"label": "Eingabe", "value": EINGABE}, {"label": "Stand", "value": "Lauf vom 22.11.2026, Daten bis Schluss 20.11.2026"}]


MAIN = ("backtest_26y.py", code_main)
CHECK = ("backtest_26y_check.py", code_check)
SELF = ("make_data.py", code_self)
NB = " "


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def pct(x, d=1, sign=False):
    s = num(x * 100, d)
    if sign and x > 0:
        s = "+" + s
    return s + f"{NB}%"


def tsd(n):
    return f"{n:,}".replace(",", NB)


def dat(s):
    y, m, d = s.split("-")
    return f"{d}.{m}.{y}"


def write(name, rows, *codes):
    (out / f"{name}.json").write_text(json.dumps({"rows": rows, "meta": meta(*codes)}, ensure_ascii=False))
    print(f"{name}: {len(rows)} Zeilen, {(out / f'{name}.json').stat().st_size / 1024:.1f} KB")


t1, t2, t3, t4, n = res["teil1"], res["teil2"], res["teil3"], res["teil4"], res["nachtrag"]
rg = t3["regeln"]
top = max(t1["jahre"], key=lambda r: r["warn_treffer"])
runs_known = [x for x in t4 if x["treffer_erster_tag"] is not None]
K = [
    ("jahre", num(res["jahre"]), res["jahre"], "Länge des Zeitraums in Jahren"),
    ("handelstage", tsd(res["tage"]), res["tage"], "Handelstage im Zeitraum"),
    ("warn_quote", pct(t1["warn"]["quote"]), t1["warn"]["quote"], "Anteil der Tage im Warnzustand mit Rückgang ≥ 5 % binnen 45 Sessions"),
    ("basis", pct(t1["basis"]), t1["basis"], "Dieselbe Quote an allen Tagen nahe Hoch (Gate an)"),
    ("warn_tage", tsd(t1["warn"]["tage"]), t1["warn"]["tage"], "Tage im Warnzustand mit bekanntem Ausgang"),
    ("warn_treffer", tsd(t1["warn"]["treffer"]), t1["warn"]["treffer"], "davon Treffer"),
    ("p_warn", num(t1["warn"]["p_shift"], 3), t1["warn"]["p_shift"], "Shift-Test Warnzustand gegen Basisrate"),
    ("erstsignal", f"{t1['erstsignal_ab3'][0]} von {t1['erstsignal_ab3'][1]}", t1["erstsignal_ab3"][0] / t1["erstsignal_ab3"][1],
     "Treffer am ersten Tag einer Episode mit Level ≥ 3"),
    ("top_jahr", str(top["jahr"]), top["jahr"], "Jahr mit den meisten Treffern im Warnzustand"),
    ("top_jahr_treffer", str(top["warn_treffer"]), top["warn_treffer"], "Treffer im Warnzustand in diesem Jahr"),
    ("korr_n", str(t2["n"]), t2["n"], "Korrekturen ≥ 5 % ab einem 252-Tage-Hoch"),
    ("korr_text", f"{t2['gewarnt_ab3']} von {t2['n']}", t2["gewarnt_ab3"], "davon mit Warnzustand zwischen 20 Sessions vor dem Hoch und dem −5-%-Tag"),
    ("zufall_warn", num(n["zufall_gate_ab3"]["mittel"]), n["zufall_gate_ab3"]["mittel"], "Mittel bei zufällig platziertem Warnzustand nahe Hoch"),
    ("p_korr", num(n["zufall_gate_ab3"]["p"], 3), n["zufall_gate_ab3"]["p"], "Anteil der Zufallsplatzierungen mit mindestens so vielen erkannten Korrekturen"),
    ("korr_zwei_text", f"{t2['gewarnt_ab2']} von {t2['n']}", t2["gewarnt_ab2"], "erkannt mit mindestens 2 Bestätigungen"),
    ("zufall_zwei", num(n["zufall_gate_ab2"]["mittel"]), n["zufall_gate_ab2"]["mittel"], "Zufallsmittel dazu"),
    ("p_korr_zwei", num(n["zufall_gate_ab2"]["p"], 3), n["zufall_gate_ab2"]["p"], "p-Wert dazu"),
    ("vor_hoch", str(n["vor_dem_hoch_ab3"]), n["vor_dem_hoch_ab3"], "Korrekturen, bei denen der Warnzustand schon bis zum Tag des Hochs anlag"),
    ("korr10_text", f"{t2['ab10']['gewarnt_ab3']} von {t2['ab10']['n']}", t2["ab10"]["gewarnt_ab3"], "Korrekturen ≥ 10 % mit Warnzustand vorher"),
    ("vorlauf", num(t2["vorlauf_median_ab3"]), t2["vorlauf_median_ab3"], "Median Sessions vom ersten Warn-Tag bis −5 %"),
    ("b0_rendite", pct(rg["B0"]["rendite_pa"]), rg["B0"]["rendite_pa"], "Buy and Hold, Rendite pro Jahr"),
    ("o1_rendite", pct(rg["O1"]["rendite_pa"]), rg["O1"]["rendite_pa"], "Kasse an Warnzustand-Tagen, Rendite pro Jahr"),
    ("o2_rendite", pct(rg["O2"]["rendite_pa"]), rg["O2"]["rendite_pa"], "45 Sessions Kasse je Warnung, Rendite pro Jahr"),
    ("o2_diff", num((rg["B0"]["rendite_pa"] - rg["O2"]["rendite_pa"]) * 100) + " Prozentpunkte",
     rg["B0"]["rendite_pa"] - rg["O2"]["rendite_pa"], "Renditeabstand O2 zu Buy and Hold pro Jahr"),
    ("o1_diff", num((rg["O1"]["rendite_pa"] - rg["B0"]["rendite_pa"]) * 100) + " Prozentpunkte",
     rg["O1"]["rendite_pa"] - rg["B0"]["rendite_pa"], "Renditevorsprung O1 vor Buy and Hold pro Jahr"),
    ("b0_dd", pct(rg["B0"]["max_dd"]), rg["B0"]["max_dd"], "Buy and Hold, größter Rückgang"),
    ("o1_dd", pct(rg["O1"]["max_dd"]), rg["O1"]["max_dd"], "O1, größter Rückgang"),
    ("o2_dd", pct(rg["O2"]["max_dd"]), rg["O2"]["max_dd"], "O2, größter Rückgang"),
    ("b1_dd", pct(rg["B1"]["max_dd"]), rg["B1"]["max_dd"], "200-Tage-Linie, größter Rückgang"),
    ("o1_p", num(t3["zufall"]["O1"]["p_rendite"], 3), t3["zufall"]["O1"]["p_rendite"], "O1 gegen zufällig verschobene Kassentage (alle Tage)"),
    ("o1_p_gate", num(n["o1"]["zufall_gate"]["p"], 3), n["o1"]["zufall_gate"]["p"], "O1 gegen zufällige Kassentage nur nahe Hoch"),
    ("o1_tage", tsd(n["o1"]["tage"]), n["o1"]["tage"], "Kassentage bei O1"),
    ("o1_ohne5", pct(n["o1"]["rendite_ohne_top5"]), n["o1"]["rendite_ohne_top5"], "O1 ohne die fünf größten vermiedenen Verlusttage"),
    ("o1_lag2", pct(n["o1"]["verzoegerung"]["2"]), n["o1"]["verzoegerung"]["2"], "O1 bei zwei Tagen Verzögerung"),
    ("o1_lag4", pct(n["o1"]["verzoegerung"]["4"]), n["o1"]["verzoegerung"]["4"], "O1 bei vier Tagen Verzögerung"),
    ("o1_besser", str(n["o1"]["jahre_besser"]), n["o1"]["jahre_besser"], "Jahre, in denen O1 besser war als Buy and Hold"),
    ("o1_schlechter", str(n["o1"]["jahre_schlechter"]), n["o1"]["jahre_schlechter"], "Jahre, in denen O1 schlechter war"),
    ("laeufe_n", str(len(t4)), len(t4), "Läufe im Warnzustand"),
    ("qqq_warn", pct(t1["qqq"]["q5_warn"]), t1["qqq"]["q5_warn"], "QQQ ≥ 5 % Rückgang binnen 45 Sessions, Warnzustand"),
    ("qqq_gate", pct(t1["qqq"]["q5_gate"]), t1["qqq"]["q5_gate"], "QQQ ≥ 5 % Rückgang, alle Tage nahe Hoch"),
]
write("kennzahlen", [{"id": a, "anzeige": b, "wert": c, "beschreibung": d} for a, b, c, d in K], MAIN, CHECK, SELF)

lv = [{"zustand": f"Level {x['level']}", "art": "level", "tage": x["tage"], "treffer": x["treffer"]} for x in t1["je_level"]]
lv.append({"zustand": "Warnzustand (≥ 3)", "art": "warn", "tage": t1["warn"]["tage"], "treffer": t1["warn"]["treffer"]})
lv.append({"zustand": "Alle Tage nahe Hoch", "art": "basis", "tage": t1["gate_tage"], "treffer": round(t1["basis"] * t1["gate_tage"])})
for x in lv:
    x["quote"] = round(x["treffer"] / x["tage"], 6)
    x["quote_anzeige"] = pct(x["quote"])
    x["tage_anzeige"] = tsd(x["tage"])
write("level", lv, MAIN, SELF)

by = {r["jahr"]: r for r in t1["jahre"]}
jr = []
for y in range(2000, 2027):
    r = by.get(y, {"gate_tage": 0, "warn_tage": 0, "warn_treffer": 0, "basis": None})
    jr.append({"jahr": str(y), "gate_tage": r["gate_tage"], "warn_tage": r["warn_tage"], "warn_treffer": r["warn_treffer"],
               "warn_ohne": r["warn_tage"] - r["warn_treffer"], "basis_anzeige": "–" if r["basis"] is None else pct(r["basis"])})
write("jahre", jr, MAIN, SELF)

ko = []
for x in t2["liste"]:
    ko.append({"hoch": x["hoch"], "hoch_anzeige": dat(x["hoch"]), "minus5_anzeige": dat(x["minus5"]),
               "tiefe": pct(x["tiefe"]) + (" (läuft)" if x["offen"] else ""), "tiefe_wert": round(x["tiefe"], 4),
               "vorlauf_warn": "–" if x["vorlauf_ab3"] is None else str(int(x["vorlauf_ab3"])),
               "vorlauf_zwei": "–" if x["vorlauf_ab2"] is None else str(int(x["vorlauf_ab2"])),
               "gewarnt": "ja" if x["vorlauf_ab3"] is not None else "nein"})
write("korrekturen", ko, MAIN, SELF)

NAMES = {"B0": "Buy and Hold", "O1": "Kasse im Warnzustand", "O2": "45 Sessions Kasse je Warnung",
         "O3": "45 Sessions halbe Position", "B1": "Nur über der 200-Tage-Linie"}
rr = []
for k in ("B0", "O1", "O2", "O3", "B1"):
    m = rg[k]
    rr.append({"regel": k, "name": f"{k} {NAMES[k]}", "rendite": pct(m["rendite_pa"]), "vola": pct(m["vola"]), "sharpe": num(m["sharpe"], 2),
               "max_dd": pct(m["max_dd"]), "investiert": pct(m["investiert"], 0), "ausstiege": str(m["ausstiege"]),
               "endwert": tsd(round(m["endwert"])), "rendite_wert": round(m["rendite_pa"], 6), "max_dd_wert": round(m["max_dd"], 6)})
write("regeln", rr, MAIN, SELF)

ku = t3["kurven"]
write("kurven", [{"datum": d, **{k: ku[k][i] for k in ("B0", "O1", "O2", "O3", "B1")}} for i, d in enumerate(ku["datum"])], MAIN, SELF)
write("spy", [{"datum": d, "schluss": v} for d, v in zip(res["spy_woche"]["datum"], res["spy_woche"]["schluss"])], MAIN, SELF)

la = []
for x in t4:
    tr = x["treffer_erster_tag"]
    la.append({"von_iso": x["von"], "bis_iso": x["bis"], "von": dat(x["von"]), "bis": dat(x["bis"]), "tage": str(x["tage"]),
               "max_level": str(x["max_level"]), "komponenten": x["komponenten"],
               "dip45": "–" if x["dip45"] is None else pct(x["dip45"]) + ("" if x["fenster_voll"] else " (läuft)"),
               "fwd45": "offen" if x["fwd45"] is None else pct(x["fwd45"], sign=True),
               "treffer": "offen" if tr is None else ("ja" if tr == 1 else "nein")})
write("laeufe", la, MAIN, SELF)
print("Kennzahlen:", {a: b for a, b, _, _ in K})
