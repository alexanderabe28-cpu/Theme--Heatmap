"""Schreibt site/index.html (statischer Text, Zahlen als Zeichnungen)."""
from pathlib import Path


def k(i, tag="span", cls=""):
    c = f' class="{cls}"' if cls else ""
    return f'<{tag}{c} data-draw="kpi" data-source="kennzahlen" data-field="anzeige" data-where="id={i}">—</{tag}>'


def th(cols):
    return "".join(f'<th data-field="{f}">{t}</th>' for f, t in cols)


CSS = """
.crb{display:grid;gap:var(--cds-gap-xl);color:var(--color-fg);font-family:var(--font-anthropic-sans);font-size:var(--cds-font-size-body);line-height:1.5;max-width:1080px}
.crb h1{font-family:var(--font-anthropic-serif);font-weight:400;font-size:var(--cds-font-size-title);line-height:1.2;margin:0 0 var(--cds-gap-sm)}
.crb h2{font-size:var(--cds-font-size-heading);font-weight:var(--cds-font-weight-medium);line-height:1.3;margin:0 0 var(--cds-gap-xs)}
.crb p{margin:0 0 var(--cds-gap-sm)}
.crb>*{min-width:0}
.crb-lead{font-size:var(--cds-font-size-heading);line-height:1.45}
.crb-note{color:var(--color-fg-muted);font-size:var(--cds-font-size-caption)}
.crb-cards{display:grid;gap:var(--cds-gap-md);grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.crb-card{background:var(--color-panel);border:1px solid var(--color-border-line);border-radius:var(--cds-radius);padding:var(--cds-pad-lg);min-width:0}
.crb-label{font-size:var(--cds-font-size-caption);color:var(--color-fg-muted)}
.crb-big{font-family:var(--font-anthropic-serif);font-weight:400;font-size:1.9rem;line-height:1.2;font-variant-numeric:tabular-nums;margin:2px 0}
.crb-chart{position:relative;min-height:240px}
.crb-chart svg{display:block;width:100%;height:auto;overflow:visible}
.crb-chart text{fill:var(--cds-text-secondary);font-family:var(--font-anthropic-sans);font-size:var(--cds-font-size-caption);font-variant-numeric:tabular-nums}
.crb-chart .crb-end{fill:var(--color-fg);font-weight:var(--cds-font-weight-medium)}
.crb-grid{stroke:var(--cds-chart-grid);stroke-width:1}
.crb-axis{stroke:var(--cds-chart-axis);stroke-width:1}
.crb-rule{stroke:var(--cds-chart-reference);stroke-width:1}
.crb-tip{position:absolute;pointer-events:none;z-index:2;background:var(--cds-surface-popover);border:1px solid var(--cds-border);box-shadow:var(--cds-shadow-popover);border-radius:var(--cds-radius);padding:6px 8px;font-size:var(--cds-font-size-caption);line-height:1.4;white-space:nowrap;font-variant-numeric:tabular-nums}
.crb-tip .crb-tip-head{color:var(--cds-text-secondary)}
.crb-bars{display:grid;gap:var(--cds-gap-sm);min-height:240px}
.crb-bar-head{display:flex;justify-content:space-between;gap:var(--cds-gap-sm);font-size:var(--cds-font-size-caption);font-variant-numeric:tabular-nums}
.crb-bar-track{height:10px;border-radius:5px;background:var(--color-panel);border:1px solid var(--color-border-line);overflow:hidden}
.crb-bar-fill{height:100%;border-radius:0 4px 4px 0}
.crb-bar-strong .crb-bar-head{font-weight:var(--cds-font-weight-medium)}
.crb-legend{display:flex;flex-wrap:wrap;gap:4px var(--cds-gap-md);list-style:none;margin:0 0 var(--cds-gap-xs);padding:0;font-size:var(--cds-font-size-caption);color:var(--color-fg-muted)}
.crb-legend li{display:flex;align-items:center;gap:6px}
.crb-sw{display:inline-block;width:10px;height:10px;border-radius:2px}
.crb-scroll{overflow-x:auto}
.crb table{border-collapse:collapse;width:100%;font-size:var(--cds-font-size-caption);font-variant-numeric:tabular-nums}
.crb th,.crb td{text-align:right;padding:6px 10px;border-bottom:1px solid var(--color-border-line);white-space:nowrap}
.crb th{color:var(--color-fg-muted);font-weight:var(--cds-font-weight-medium)}
.crb th:first-child,.crb td:first-child{text-align:left;padding-left:0}
.crb details{border-top:1px solid var(--color-border-line);padding-top:var(--cds-gap-sm)}
.crb summary{cursor:pointer;font-weight:var(--cds-font-weight-medium)}
.crb details ul{margin:var(--cds-gap-sm) 0 0;padding-left:1.2em}
.crb details li{margin-bottom:6px}
@media print{.crb details{break-before:page}.crb-scroll{overflow:visible}}
"""

KORR = [("hoch_anzeige", "Hoch"), ("minus5_anzeige", "−5 % am"), ("tiefe", "Tiefe"),
        ("vorlauf_warn", "Warnzustand vorher"), ("vorlauf_zwei", "≥ 2 Bestätigungen vorher")]
REGELN = [("name", "Regel"), ("rendite", "Rendite p. a."), ("vola", "Volatilität"), ("sharpe", "Sharpe"),
          ("max_dd", "Größter Rückgang"), ("investiert", "Investiert"), ("ausstiege", "Ausstiege")]
LAEUFE = [("von", "Von"), ("bis", "Bis"), ("tage", "Tage"), ("max_level", "Höchstes Level"), ("komponenten", "Komponenten"),
          ("dip45", "Schlechtester Dip, 45 Sessions"), ("fwd45", "Rendite nach 45 Sessions"), ("treffer", "Treffer am ersten Tag")]

HTML = f"""<meta name="dash-one-writer">
<style>{CSS}</style>
<div class="crb" lang="de">
<header id="kopf">
<h1 id="titel">Correction Risk: Backtest 2000–2026</h1>
<p class="crb-lead" id="fazit">Im Warnzustand folgte an {k('warn_quote', 'b')} der Tage binnen 45 Sessions ein Rückgang von mindestens 5 %, an allen Tagen nahe Hoch waren es {k('basis', 'b')}. Zum Aussteigen taugt das Signal trotzdem nicht: 45 Sessions in Kasse kosteten {k('o2_diff', 'b')} Rendite pro Jahr.</p>
<p class="crb-note" id="rahmen">SPY, Tagesschlusskurse vom 03.01.2000 bis 20.11.2026, das sind {k('jahre')} Jahre und {k('handelstage')} Handelstage. Das Modell ist unverändert (Spec v1.1): Gate nahe Hoch, vier Bestätigungen, Warnzustand ab drei. Der Zeitraum enthält die Entwicklungsjahre 2007–2016, der Lauf beschreibt und ist kein neuer Test.</p>
</header>

<section class="crb-cards" id="kacheln">
<div class="crb-card" id="k-quote"><div class="crb-label">Quote im Warnzustand</div>{k('warn_quote', 'div', 'crb-big')}<div class="crb-note">Basisrate {k('basis')} · {k('warn_tage')} Tage</div></div>
<div class="crb-card" id="k-korr"><div class="crb-label">Korrekturen mit Warnung vorher</div>{k('korr_text', 'div', 'crb-big')}<div class="crb-note">Zufall nahe Hoch: {k('zufall_warn')}</div></div>
<div class="crb-card" id="k-o1"><div class="crb-label">Kasse nur an Warnzustand-Tagen</div>{k('o1_rendite', 'div', 'crb-big')}<div class="crb-note">pro Jahr · Buy and Hold {k('b0_rendite')}</div></div>
<div class="crb-card" id="k-o2"><div class="crb-label">45 Sessions Kasse je Warnung</div>{k('o2_rendite', 'div', 'crb-big')}<div class="crb-note">pro Jahr · größter Rückgang {k('o2_dd')}</div></div>
</section>

<section id="s-verlauf">
<h2 id="h-verlauf">Wann der Warnzustand anlag</h2>
<p class="crb-note">SPY-Wochenschluss, logarithmisch. Die Bänder markieren die {k('laeufe_n')} Läufe im Warnzustand.</p>
<div class="crb-chart" id="c-verlauf" data-draw="chart_spy" data-source="spy laeufe">—</div>
</section>

<section id="s-level">
<h2 id="h-level">Quote je Level</h2>
<p class="crb-note">Anteil der Tage, denen binnen 45 Sessions ein Schluss mindestens 5 % unter dem Tagesschluss folgte. Am ersten Tag einer Episode waren es nur {k('erstsignal')}. Shift-Test für den Warnzustand: p = {k('p_warn')}.</p>
<div class="crb-bars" id="c-level" data-draw="chart_level" data-source="level">—</div>
</section>

<section id="s-jahre">
<h2 id="h-jahre">Die Treffer klumpen in wenigen Jahren</h2>
<p class="crb-note">Tage im Warnzustand je Jahr. {k('top_jahr')} allein liefert {k('top_jahr_treffer')} der {k('warn_treffer')} Treffer.</p>
<ul class="crb-legend" id="l-jahre"><li><i class="crb-sw" data-c="0"></i>Treffer</li><li><i class="crb-sw" data-c="muted"></i>kein Treffer</li></ul>
<div class="crb-chart" id="c-jahre" data-draw="chart_jahre" data-source="jahre">—</div>
</section>

<section id="s-korr">
<h2 id="h-korr">Alle {k('korr_n')} Korrekturen ab Hoch</h2>
<p id="p-korr">Vor {k('korr_text', 'b')} Rückgängen von mindestens 5 % lag der Warnzustand an, bei Rückgängen ab 10 % waren es {k('korr10_text', 'b')}. Ein zufällig platzierter Warnzustand nahe Hoch erwischt im Mittel {k('zufall_warn', 'b')} (p = {k('p_korr')}). Mit mindestens 2 Bestätigungen sind es {k('korr_zwei_text', 'b')}, der Zufall schafft {k('zufall_zwei', 'b')} (p = {k('p_korr_zwei')}). Schon bis zum Tag des Hochs lag der Warnzustand nur in {k('vor_hoch', 'b')} Fällen an, sonst kam er erst im beginnenden Rückgang.</p>
<div class="crb-scroll"><table id="t-korr" data-source="korrekturen" data-row-key="hoch"><thead><tr>{th(KORR)}</tr></thead><tbody data-draw="rows_korr"></tbody></table></div>
<p class="crb-note">Vorlauf in Sessions vom ersten Warn-Tag bis zum ersten Schluss 5 % unter dem Hoch, gezählt ab 20 Sessions vor dem Hoch. Ein Strich heißt: keine Warnung vorher. Median Vorlauf im Warnzustand: {k('vorlauf')} Sessions.</p>
</section>

<section id="s-ausstieg">
<h2 id="h-ausstieg">Aussteigen im Warnzustand</h2>
<p id="p-o1">Kasse nur an den Tagen im Warnzustand (O1) brachte {k('o1_rendite', 'b')} pro Jahr gegen {k('b0_rendite', 'b')} bei Buy and Hold. Der Vorsprung hängt an wenigen großen Verlusttagen: Ohne die fünf größten bleiben {k('o1_ohne5')}, bei zwei Tagen Verzögerung {k('o1_lag2')}. O1 war in {k('o1_besser')} Jahren besser und in {k('o1_schlechter')} schlechter. Zufallsvergleich: p = {k('o1_p')} über alle Tage, p = {k('o1_p_gate')} nur nahe Hoch.</p>
<p id="p-o2">Wer nach einer Warnung 45 Sessions draußen bleibt (O2), landet bei {k('o2_rendite', 'b')} pro Jahr und einem größten Rückgang von {k('o2_dd')}. Schutz im Bärenmarkt gibt es nicht, weil das Modell nur nahe Hoch misst: Buy and Hold {k('b0_dd')}, die 200-Tage-Linie {k('b1_dd')}.</p>
<ul class="crb-legend" id="l-kurven"><li><i class="crb-sw" data-c="0"></i>B0 Buy and Hold</li><li><i class="crb-sw" data-c="1"></i>O1 Kasse im Warnzustand</li><li><i class="crb-sw" data-c="2"></i>O2 45 Sessions Kasse</li><li><i class="crb-sw" data-c="3"></i>O3 45 Sessions halbe Position</li><li><i class="crb-sw" data-c="4"></i>B1 200-Tage-Linie</li></ul>
<div class="crb-chart" id="c-kurven" data-draw="chart_kurven" data-source="kurven">—</div>
<p class="crb-note">Wertentwicklung aus 100, logarithmisch, Monatsende. Signal zum Schluss, Umsetzung zum Schluss des Folgetags, Kasse verzinst mit dem 13-Wochen-T-Bill, ohne Kosten und Steuern.</p>
<div class="crb-scroll"><table id="t-regeln" data-source="regeln" data-row-key="regel"><thead><tr>{th(REGELN)}</tr></thead><tbody data-draw="rows_regeln"></tbody></table></div>
</section>

<details id="d-laeufe">
<summary>Alle Läufe im Warnzustand</summary>
<div class="crb-scroll"><table id="t-laeufe" data-source="laeufe" data-row-key="von_iso"><thead><tr>{th(LAEUFE)}</tr></thead><tbody data-draw="rows_laeufe"></tbody></table></div>
</details>

<details id="d-methodik">
<summary>Methodik und Grenzen</summary>
<ul>
<li>Gate: SPY-Schluss höchstens 3 % unter dem 252-Tage-Schlusshoch. Bestätigungen: Credit (HYG/IEF), Breadth (RSP), Rotation (XLY/XLP), Volatility (VIX), jeweils auf der Risk-off-Seite des 50-Tage-SMA mit 20-Tage-Veränderung in dieselbe Richtung.</li>
<li>Treffer: Der tiefste SPY-Schluss der nächsten 45 Sessions liegt mindestens 5 % unter dem Tagesschluss.</li>
<li>Korrektur ab Hoch: Schluss mindestens 5 % unter einem 252-Tage-Schlusshoch, bevor ein neues entsteht.</li>
<li>Zufallsvergleich: Die Warn-Tage werden innerhalb der Tage nahe Hoch zirkulär verschoben. Der vorab festgelegte Vergleich über alle Tage ist zu milde, weil Warnungen nur nahe Hoch entstehen können.</li>
<li>Vor Auflage der ETFs laufen verkettete Fondsreihen (VWEHX, VFITX, VADAX). 1999–2007 war der blinde Test des Modells, dort fiel es durch.</li>
<li>Mit QQQ als Ziel: {k('qqq_warn')} im Warnzustand gegen {k('qqq_gate')} an allen Tagen nahe Hoch.</li>
<li>Alle Regeln wurden vor dem Lauf festgelegt und stehen hier, auch die schlechten. Die Auswertung nach Verzögerung und ohne die größten Verlusttage kam nach dem Lauf dazu.</li>
</ul>
</details>
</div>
<script src="report.js"></script>
"""
HTML = "\n".join(l for l in HTML.replace('"', "'").splitlines() if l.strip()) + "\n"
assert '"' not in HTML and "\\" not in HTML
Path("site/index.html").write_text(HTML)
print(len(HTML.encode()), "Bytes index.html")
