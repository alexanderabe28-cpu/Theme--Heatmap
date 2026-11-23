(() => {
  const P = d3.utcParse('%Y-%m-%d');
  const dDay = d3.utcFormat('%d.%m.%Y');
  const dMon = d3.utcFormat('%m.%Y');
  const de = (v, n = 0) => Number(v).toFixed(n).replace('.', ',').replace('-', '−');
  const get = (id) => dash.data(id);
  const state = (...ids) => {
    const s = ids.map(get);
    if (s.some((x) => x.status === 'error')) return 'error';
    return s.every((x) => x.status === 'ok') ? 'ok' : 'wait';
  };
  const FAIL = 'Die Daten für diesen Teil konnten nicht geladen werden.';
  const KEYS = ['B0', 'O1', 'O2', 'O3', 'B1'];
  const color = (c) => (c === 'muted' ? 'var(--cds-chart-muted)' : dash.colors[+c % dash.colors.length]);
  const blank = (el, st) => {
    el.replaceChildren();
    el.textContent = st === 'error' ? FAIL : '—';
  };

  // Legendenfarben: ausserhalb von Zeichnungen setzt das Skript nur style
  dash.onData(() => {
    document.querySelectorAll('.crb-sw').forEach((sw) => {
      sw.style.background = color(sw.getAttribute('data-c'));
    });
  });

  // Einzelne Zahlen aus der Kennzahlen-Tabelle
  dash.draw('kpi', (el) => {
    const s = get('kennzahlen');
    const [col, val] = (el.getAttribute('data-where') || '').split('=');
    const r = s.status === 'ok' ? s.data.find((x) => String(x[col]) === val) : null;
    el.textContent = r ? String(r[el.getAttribute('data-field')]) : '—';
  });

  // Tabellen
  const rowsTable = (name, id, key, cols) => dash.draw(name, (tb) => {
    const st = state(id);
    tb.replaceChildren();
    if (st !== 'ok') {
      if (st === 'error') {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = cols.length;
        td.textContent = FAIL;
        tr.append(td);
        tb.append(tr);
      }
      return;
    }
    for (const r of get(id).data) {
      const tr = document.createElement('tr');
      tr.setAttribute('data-key', String(r[key]));
      for (const c of cols) {
        const td = document.createElement('td');
        td.textContent = r[c] == null ? '' : String(r[c]);
        tr.append(td);
      }
      tb.append(tr);
    }
  });
  rowsTable('rows_korr', 'korrekturen', 'hoch', ['hoch_anzeige', 'minus5_anzeige', 'tiefe', 'vorlauf_warn', 'vorlauf_zwei']);
  rowsTable('rows_regeln', 'regeln', 'regel', ['name', 'rendite', 'vola', 'sharpe', 'max_dd', 'investiert', 'ausstiege']);
  rowsTable('rows_laeufe', 'laeufe', 'von_iso', ['von', 'bis', 'tage', 'max_level', 'komponenten', 'dip45', 'fwd45', 'treffer']);

  // Quote je Level als Balkenliste
  dash.draw('chart_level', (el) => {
    const st = state('level');
    if (st !== 'ok') return blank(el, st);
    el.replaceChildren();
    const rows = get('level').data;
    const max = d3.max(rows, (r) => +r.quote) || 1;
    for (const r of rows) {
      const row = document.createElement('div');
      row.className = r.art === 'warn' ? 'crb-bar-strong' : 'crb-bar';
      const head = document.createElement('div');
      head.className = 'crb-bar-head';
      const a = document.createElement('span');
      a.textContent = r.zustand;
      const b = document.createElement('span');
      b.textContent = `${r.quote_anzeige} · ${r.tage_anzeige} Tage`;
      head.append(a, b);
      const track = document.createElement('div');
      track.className = 'crb-bar-track';
      const fill = document.createElement('div');
      fill.className = 'crb-bar-fill';
      fill.style.width = `${(+r.quote / max) * 100}%`;
      fill.style.background = r.art === 'basis' ? 'var(--cds-chart-muted)' : dash.colors[0];
      track.append(fill);
      row.append(head, track);
      el.append(row);
    }
  });

  // Hilfen fuer SVG-Charts
  const tipFor = (el) => {
    const t = document.createElement('div');
    t.className = 'crb-tip';
    t.hidden = true;
    el.append(t);
    return {
      show(px, py, head, lines) {
        t.replaceChildren();
        const h = document.createElement('div');
        h.className = 'crb-tip-head';
        h.textContent = head;
        t.append(h);
        for (const l of lines) {
          const d = document.createElement('div');
          d.textContent = l;
          t.append(d);
        }
        t.hidden = false;
        const left = Math.max(0, Math.min(px + 12, el.clientWidth - t.offsetWidth - 2));
        t.style.left = `${left}px`;
        t.style.top = `${Math.max(0, py - t.offsetHeight - 10)}px`;
      },
      hide() {
        t.hidden = true;
      },
    };
  };
  const widest = (svg, labels) => {
    const t = svg.append('text').style('visibility', 'hidden');
    let m = 0;
    for (const s of labels) {
      t.text(s);
      m = Math.max(m, t.node().getComputedTextLength());
    }
    t.remove();
    return m;
  };
  const frame = (el, label, ratio, lo, hi) => {
    el.replaceChildren();
    const W = Math.max(260, el.clientWidth || 600);
    const H = Math.round(Math.max(lo, Math.min(hi, W * ratio)));
    const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', label);
    return {W, H, svg};
  };
  const yAxis = (svg, ticks, y, m, W, fmt) => {
    const g = svg.append('g');
    g.selectAll('line').data(ticks).join('line').attr('class', 'crb-grid')
      .attr('x1', m.l).attr('x2', W - m.r).attr('y1', (v) => y(v)).attr('y2', (v) => y(v));
    g.selectAll('text').data(ticks).join('text').attr('x', m.l - 6).attr('y', (v) => y(v)).attr('dy', '0.32em')
      .attr('text-anchor', 'end').text(fmt);
  };
  const timeAxis = (svg, x, m, W, H) => {
    const step = W < 420 ? 5 : W < 760 ? 4 : 2;
    svg.append('g').selectAll('text').data(x.ticks(d3.utcYear.every(step))).join('text')
      .attr('x', (d) => x(d)).attr('y', H - 6).attr('text-anchor', 'middle').text((d) => d.getUTCFullYear());
    svg.append('line').attr('class', 'crb-axis').attr('x1', m.l).attr('x2', W - m.r).attr('y1', H - m.b).attr('y2', H - m.b);
  };

  // SPY mit Warnzustand-Baendern
  dash.draw('chart_spy', (el) => {
    const st = state('spy', 'laeufe');
    if (st !== 'ok') return blank(el, st);
    const pts = get('spy').data.map((d) => ({t: P(d.datum), v: +d.schluss})).filter((d) => d.t && d.v > 0);
    const runs = get('laeufe').data.map((d) => ({a: P(d.von_iso), b: P(d.bis_iso)})).filter((d) => d.a && d.b);
    if (!pts.length) return blank(el, 'wait');
    const {W, H, svg} = frame(el, 'SPY-Wochenschluss seit 2000, logarithmisch, mit markierten Phasen im Warnzustand', 0.45, 240, 380);
    const lo = d3.min(pts, (d) => d.v);
    const hi = d3.max(pts, (d) => d.v);
    const ticks = [50, 100, 200, 400, 800].filter((v) => v >= lo * 0.92 && v <= hi * 1.06);
    const m = {t: 8, r: 10, b: 22, l: Math.ceil(widest(svg, ticks.map((v) => de(v)))) + 8};
    const x = d3.scaleUtc().domain(d3.extent(pts, (d) => d.t)).range([m.l, W - m.r]);
    const y = d3.scaleLog().domain([lo * 0.92, hi * 1.06]).range([H - m.b, m.t]);
    yAxis(svg, ticks, y, m, W, (v) => de(v));
    svg.append('g').selectAll('rect').data(runs).join('rect')
      .attr('x', (d) => x(d.a) - 0.75).attr('width', (d) => Math.max(1.5, x(d.b) - x(d.a) + 1.5))
      .attr('y', m.t).attr('height', H - m.b - m.t)
      .style('fill', 'var(--cds-chart-status-critical)').style('opacity', 0.4);
    timeAxis(svg, x, m, W, H);
    svg.append('path').datum(pts).attr('fill', 'none').style('stroke', dash.colors[0]).attr('stroke-width', 2)
      .attr('stroke-linejoin', 'round').attr('d', d3.line().x((d) => x(d.t)).y((d) => y(d.v)));
    const rule = svg.append('line').attr('class', 'crb-rule').attr('y1', m.t).attr('y2', H - m.b).style('display', 'none');
    const dot = svg.append('circle').attr('r', 4).style('fill', dash.colors[0]).style('stroke', 'var(--color-bg)')
      .attr('stroke-width', 2).style('display', 'none');
    const tip = tipFor(el);
    const near = d3.bisector((d) => d.t).center;
    svg.append('rect').attr('x', m.l).attr('y', m.t).attr('width', W - m.l - m.r).attr('height', H - m.b - m.t)
      .attr('fill', 'transparent')
      .on('pointermove', (ev) => {
        const d = pts[near(pts, x.invert(d3.pointer(ev, svg.node())[0]))];
        if (!d) return;
        const warn = runs.some((r) => d.t >= r.a && d3.utcDay.offset(d.t, -6) <= r.b);
        rule.style('display', null).attr('x1', x(d.t)).attr('x2', x(d.t));
        dot.style('display', null).attr('cx', x(d.t)).attr('cy', y(d.v));
        const [px, py] = d3.pointer(ev, el);
        tip.show(px, py, `Woche bis ${dDay(d.t)}`, [`SPY ${de(d.v, 2)}`].concat(warn ? ['Warnzustand in dieser Woche'] : []));
      })
      .on('pointerleave', () => {
        rule.style('display', 'none');
        dot.style('display', 'none');
        tip.hide();
      });
  });

  // Warnzustand-Tage je Jahr
  dash.draw('chart_jahre', (el) => {
    const st = state('jahre');
    if (st !== 'ok') return blank(el, st);
    const rows = get('jahre').data.map((d) => ({j: String(d.jahr), hit: +d.warn_treffer, miss: +d.warn_ohne}));
    if (!rows.length) return blank(el, 'wait');
    const {W, H, svg} = frame(el, 'Tage im Warnzustand je Jahr, geteilt in Treffer und kein Treffer', 0.4, 220, 320);
    const y = d3.scaleLinear().domain([0, d3.max(rows, (d) => d.hit + d.miss) || 1]).nice(4);
    const ticks = y.ticks(4);
    const m = {t: 8, r: 6, b: 22, l: Math.ceil(widest(svg, ticks.map(String))) + 8};
    const x = d3.scaleBand().domain(rows.map((d) => d.j)).range([m.l, W - m.r]).paddingInner(0.25).paddingOuter(0.1);
    y.range([H - m.b, m.t]);
    yAxis(svg, ticks, y, m, W, String);
    const every = Math.max(1, Math.ceil((widest(svg, ['2000']) + 8) / x.step()));
    svg.append('g').selectAll('text').data(rows.filter((d, i) => i % every === 0)).join('text')
      .attr('x', (d) => x(d.j) + x.bandwidth() / 2).attr('y', H - 6).attr('text-anchor', 'middle').text((d) => d.j);
    svg.append('line').attr('class', 'crb-axis').attr('x1', m.l).attr('x2', W - m.r).attr('y1', H - m.b).attr('y2', H - m.b);
    const g = svg.append('g').selectAll('g').data(rows).join('g');
    g.append('rect').attr('x', (d) => x(d.j)).attr('width', x.bandwidth()).attr('rx', 2)
      .attr('y', (d) => y(d.hit)).attr('height', (d) => y(0) - y(d.hit)).style('fill', dash.colors[0]);
    g.append('rect').attr('x', (d) => x(d.j)).attr('width', x.bandwidth()).attr('rx', 2)
      .attr('y', (d) => y(d.hit + d.miss))
      .attr('height', (d) => Math.max(0, y(d.hit) - y(d.hit + d.miss) - (d.hit > 0 && d.miss > 0 ? 2 : 0)))
      .style('fill', 'var(--cds-chart-muted)');
    const tip = tipFor(el);
    svg.append('g').selectAll('rect').data(rows).join('rect')
      .attr('x', (d) => x(d.j) - (x.step() - x.bandwidth()) / 2).attr('width', x.step())
      .attr('y', m.t).attr('height', H - m.b - m.t).attr('fill', 'transparent')
      .on('pointermove', (ev, d) => {
        const [px, py] = d3.pointer(ev, el);
        tip.show(px, py, d.j, [`${d.hit + d.miss} Tage im Warnzustand`, `${d.hit} Treffer`]);
      })
      .on('pointerleave', () => tip.hide());
  });

  // Wertentwicklung der Regeln
  dash.draw('chart_kurven', (el) => {
    const st = state('kurven');
    if (st !== 'ok') return blank(el, st);
    const rows = get('kurven').data.map((d) => {
      const o = {t: P(d.datum)};
      for (const k of KEYS) o[k] = +d[k];
      return o;
    }).filter((d) => d.t);
    if (!rows.length) return blank(el, 'wait');
    const {W, H, svg} = frame(el, 'Wertentwicklung der fünf Regeln aus 100 seit 2000, logarithmisch', 0.5, 260, 420);
    const lo = d3.min(rows, (d) => d3.min(KEYS, (k) => d[k]));
    const hi = d3.max(rows, (d) => d3.max(KEYS, (k) => d[k]));
    const ticks = [50, 100, 200, 400, 800, 1600].filter((v) => v >= lo * 0.92 && v <= hi * 1.08);
    const m = {t: 10, r: Math.ceil(widest(svg, KEYS)) + 14, b: 22, l: Math.ceil(widest(svg, ticks.map((v) => de(v)))) + 8};
    const x = d3.scaleUtc().domain(d3.extent(rows, (d) => d.t)).range([m.l, W - m.r]);
    const y = d3.scaleLog().domain([lo * 0.92, hi * 1.08]).range([H - m.b, m.t]);
    yAxis(svg, ticks, y, m, W, (v) => de(v));
    timeAxis(svg, x, m, W, H);
    KEYS.forEach((k, i) => {
      svg.append('path').datum(rows).attr('fill', 'none').style('stroke', dash.colors[i % dash.colors.length])
        .attr('stroke-width', 2).attr('stroke-linejoin', 'round').attr('d', d3.line().x((d) => x(d.t)).y((d) => y(d[k])));
    });
    const last = rows[rows.length - 1];
    const ends = KEYS.map((k, i) => ({k, i, y0: y(last[k]), y: y(last[k])})).sort((a, b) => a.y - b.y);
    for (let i = 1; i < ends.length; i += 1) ends[i].y = Math.max(ends[i].y, ends[i - 1].y + 13);
    const over = ends[ends.length - 1].y - (H - m.b);
    if (over > 0) ends.forEach((e) => { e.y -= over; });
    const eg = svg.append('g').selectAll('g').data(ends).join('g');
    eg.append('circle').attr('cx', x(last.t)).attr('cy', (e) => e.y0).attr('r', 3)
      .style('fill', (e) => dash.colors[e.i % dash.colors.length]);
    eg.append('text').attr('class', 'crb-end').attr('x', x(last.t) + 8).attr('y', (e) => e.y).attr('dy', '0.32em').text((e) => e.k);
    const rule = svg.append('line').attr('class', 'crb-rule').attr('y1', m.t).attr('y2', H - m.b).style('display', 'none');
    const tip = tipFor(el);
    const near = d3.bisector((d) => d.t).center;
    svg.append('rect').attr('x', m.l).attr('y', m.t).attr('width', W - m.l - m.r).attr('height', H - m.b - m.t)
      .attr('fill', 'transparent')
      .on('pointermove', (ev) => {
        const d = rows[near(rows, x.invert(d3.pointer(ev, svg.node())[0]))];
        if (!d) return;
        rule.style('display', null).attr('x1', x(d.t)).attr('x2', x(d.t));
        const [px, py] = d3.pointer(ev, el);
        const lines = KEYS.slice().sort((a, b) => d[b] - d[a]).map((k) => `${k} ${de(d[k])}`);
        tip.show(px, py, `Monatsende ${dMon(d.t)}`, lines);
      })
      .on('pointerleave', () => {
        rule.style('display', 'none');
        tip.hide();
      });
  });
})();
