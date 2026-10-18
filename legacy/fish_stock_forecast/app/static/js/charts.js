/*
 * Небольшая библиотека SVG-графиков без внешних зависимостей (работает офлайн).
 *   Charts.xy(container, spec)       — столбцы / точки / линии по категориальной оси X
 *   Charts.heatmap(container, spec)  — тепловая карта (строки × столбцы)
 * Цвета берутся из CSS-переменных, поэтому светлая и тёмная темы работают сами.
 * Графики перерисовываются при изменении размера и смене темы.
 */
const Charts = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const nf = (digits) => new Intl.NumberFormat("ru-RU", { maximumFractionDigits: digits });
  const fmtAuto = (v) => {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    const a = Math.abs(v);
    return nf(a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3).format(v);
  };

  function el(tag, attrs = {}, parent = null) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  }
  function txt(parent, x, y, text, attrs = {}) {
    const t = el("text", { x, y, ...attrs }, parent);
    t.textContent = text;
    return t;
  }

  // ---------- шкалы ----------
  function niceStep(span, count) {
    const raw = span / Math.max(count, 1);
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    const m = raw / p;
    return (m >= 5 ? 10 : m >= 2 ? 5 : m >= 1 ? 2 : 1) * p;
  }
  function linearTicks(min, max, count = 5) {
    if (min === max) { max = min + 1; }
    const step = niceStep(max - min, count);
    const lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step;
    const ticks = [];
    for (let v = lo; v <= hi + step * 1e-9; v += step) ticks.push(+v.toFixed(12));
    return { lo, hi, ticks };
  }
  function logTicks(min, max) {
    const lo = Math.pow(10, Math.floor(Math.log10(min)));
    const hi = Math.pow(10, Math.ceil(Math.log10(max)));
    const ticks = [];
    const decades = Math.log10(hi / lo);
    for (let d = lo; d <= hi * 1.0001; d *= 10) {
      ticks.push(d);
      if (decades <= 2) { if (d * 2 < hi) ticks.push(d * 2); if (d * 5 < hi) ticks.push(d * 5); }
    }
    return { lo, hi, ticks: ticks.sort((a, b) => a - b) };
  }

  // ---------- подсказка ----------
  const tip = () => document.getElementById("tooltip");
  function showTip(evt, head, rows) {
    const t = tip(); if (!t) return;
    t.replaceChildren();
    const h = document.createElement("div"); h.className = "tt-head"; h.textContent = head; t.appendChild(h);
    for (const r of rows) {
      const row = document.createElement("div"); row.className = "tt-row";
      const key = document.createElement("span"); key.className = "tt-key";
      if (r.color) { const i = document.createElement("i"); i.style.borderTopColor = r.color;
        if (r.dash) i.style.borderTopStyle = "dashed"; key.appendChild(i); }
      key.appendChild(document.createTextNode(r.label));
      const b = document.createElement("b"); b.textContent = r.value;
      row.append(key, b); t.appendChild(row);
    }
    t.hidden = false;
    const pad = 14, w = t.offsetWidth, hgt = t.offsetHeight;
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + w > window.innerWidth - 8) x = evt.clientX - w - pad;
    if (y + hgt > window.innerHeight - 8) y = evt.clientY - hgt - pad;
    t.style.left = `${Math.max(8, x)}px`; t.style.top = `${Math.max(8, y)}px`;
  }
  function hideTip() { const t = tip(); if (t) t.hidden = true; }

  // ---------- перерисовка по размеру и теме ----------
  const registry = new Map();
  const ro = new ResizeObserver((entries) => {
    for (const e of entries) { const r = registry.get(e.target); if (r) r(); }
  });
  function register(container, render) {
    if (!registry.has(container)) ro.observe(container);
    registry.set(container, render);
    render();
  }
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => registry.forEach((r) => r()));

  function legend(container, items) {
    const lg = document.createElement("div"); lg.className = "legend";
    for (const it of items) {
      const s = document.createElement("span");
      const i = document.createElement("i"); i.className = `k-${it.kind}`;
      if (it.kind === "band") { i.className = "k-rect"; i.style.background = it.color; i.style.opacity = it.opacity || 0.35; }
      else if (it.kind === "rect" || it.kind === "dot") i.style.background = it.color;
      else if (it.kind !== "ref") i.style.borderTopColor = it.color;
      s.append(i, document.createTextNode(it.label)); lg.appendChild(s);
    }
    container.appendChild(lg);
    return lg;
  }

  function roundedTopBar(x, y, w, h, r) {
    r = Math.min(r, w / 2, h);
    if (h <= 0) return "";
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  }

  /* ======================================================================
   * XY-график по категориальной оси X
   * spec: { x:[...], xTitle, yTitle, yLog, yDomain:[min,max],
   *         bars:{name,values,colorVar}, points:{name,values,colorVar},
   *         lines:[{name,values,colorVar,dash,markers}],
   *         bands:[{name,lo,hi,colorVar,opacity}]              — полоса интервала (например, 50 % / 95 %),
   *         intervals:[{name,lo,hi,mid,colorVar,dx}]             — отрезок интервала с точкой в середине,
   *         lines[].noLine — только маркеры (точки данных),
   *         refs:[{y,label}], vrefs:[{x,label}], format, xLabel(v) }
   * ====================================================================== */
  function xy(container, spec) {
    register(container, () => drawXY(container, spec));
  }

  function drawXY(container, spec) {
    container.replaceChildren();
    const fmt = spec.format || fmtAuto;
    const xLabel = spec.xLabel || ((v) => String(v));

    const items = [];
    for (const b of spec.bands || []) if (b.name) items.push({ kind: "band", color: css(b.colorVar), label: b.name, opacity: b.opacity });
    if (spec.bars) items.push({ kind: "rect", color: css(spec.bars.colorVar), label: spec.bars.name });
    if (spec.points) items.push({ kind: "rect", color: css(spec.points.colorVar), label: spec.points.name });
    for (const b of spec.barGroups || []) items.push({ kind: "rect", color: css(b.colorVar), label: b.name });
    for (const d of spec.dots || []) items.push({ kind: "dot", color: css(d.colorVar), label: d.name });
    for (const l of spec.lines || []) if (l.values && l.values.some((v) => v !== null))
      items.push({ kind: l.noLine ? "dot" : l.dash ? "dash" : "line", color: css(l.colorVar), label: l.name });
    for (const iv of spec.intervals || []) if (iv.name) items.push({ kind: "dot", color: css(iv.colorVar), label: iv.name });
    if (spec.refs && spec.refs.length && spec.refsLegend) items.push({ kind: "ref", label: spec.refsLegend });
    const lg = items.length > 1 ? legend(container, items) : null;

    const W = container.clientWidth || 600;
    const H = Math.max(160, (container.clientHeight || 300) - (lg ? lg.offsetHeight + 6 : 0));
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img" }, container);
    const m = { top: 12, right: 16, bottom: 40, left: 58 };
    const pw = W - m.left - m.right, ph = H - m.top - m.bottom;

    // --- домен Y ---
    const all = [];
    const push = (arr) => (arr || []).forEach((v) => { if (v !== null && v !== undefined && Number.isFinite(v)) all.push(v); });
    if (spec.bars) push(spec.bars.values);
    if (spec.points) push(spec.points.values);
    (spec.lines || []).forEach((l) => push(l.values));
    (spec.barGroups || []).forEach((b) => push(b.values));
    (spec.dots || []).forEach((d) => push(d.points.map((p) => p.y)));
    (spec.refs || []).forEach((r) => all.push(r.y));
    (spec.bands || []).forEach((b) => { push(b.lo); push(b.hi); });
    (spec.intervals || []).forEach((iv) => { push(iv.lo); push(iv.hi); push(iv.mid); });
    let y0, y1, ticks, ys;
    if (spec.yLog) {
      const pos = all.filter((v) => v > 0);
      if (!pos.length) pos.push(1, 10);
      const lt = logTicks(Math.min(...pos), Math.max(...pos));
      y0 = lt.lo; y1 = lt.hi; ticks = lt.ticks;
      ys = (v) => m.top + ph - (Math.log10(v) - Math.log10(y0)) / (Math.log10(y1) - Math.log10(y0)) * ph;
    } else {
      if (!all.length) all.push(0, 1);
      const lo = spec.yDomain ? spec.yDomain[0] : Math.min(0, ...all);
      const hi = spec.yDomain ? spec.yDomain[1] : Math.max(...all);
      const lt = spec.yDomain ? { lo, hi, ticks: linearTicks(lo, hi, 5).ticks.filter((t) => t >= lo - 1e-9 && t <= hi + 1e-9) }
                              : linearTicks(lo, hi, 5);
      y0 = lt.lo; y1 = lt.hi; ticks = lt.ticks;
      ys = (v) => m.top + ph - (v - y0) / (y1 - y0) * ph;
    }
    const n = spec.x.length, band = pw / n;
    const xs = (i) => m.left + band * (i + 0.5);

    // --- сетка и оси ---
    const grid = el("g", { class: "grid" }, svg);
    for (const t of ticks) {
      const y = ys(t);
      el("line", { x1: m.left, x2: m.left + pw, y1: y, y2: y }, grid);
      txt(svg, m.left - 8, y + 4, fmt(t), { "text-anchor": "end" });
    }
    const axis = el("g", { class: "axis" }, svg);
    el("line", { x1: m.left, x2: m.left + pw, y1: m.top + ph, y2: m.top + ph }, axis);
    const maxLen = Math.max(1, ...spec.x.map((v) => String(xLabel(v)).length));
    const every = Math.ceil(Math.max(spec.xLabel ? 36 : 28, maxLen * 7 + 8) / band);
    spec.x.forEach((v, i) => { if (i % every === 0) txt(svg, xs(i), m.top + ph + 16, xLabel(v), { "text-anchor": "middle" }); });
    if (spec.xTitle) txt(svg, m.left + pw / 2, H - 4, spec.xTitle, { "text-anchor": "middle", class: "axis-title" });
    if (spec.yTitle) txt(svg, 12, m.top + ph / 2, spec.yTitle, {
      "text-anchor": "middle", class: "axis-title", transform: `rotate(-90 12 ${m.top + ph / 2})` });

    // --- опорные линии ---
    for (const r of spec.refs || []) {
      const y = ys(r.y);
      el("line", { x1: m.left, x2: m.left + pw, y1: y, y2: y, stroke: css("--ref"), "stroke-width": 1 }, svg);
      if (r.label) txt(svg, m.left + pw - 2, y - 4, r.label, { "text-anchor": "end", class: "ref-label" });
    }
    for (const r of spec.vrefs || []) {
      const i = spec.x.indexOf(r.x);
      const pos = i >= 0 ? xs(i) : m.left + band * (r.x - spec.x[0] + 0.5);
      if (pos < m.left || pos > m.left + pw) continue;
      el("line", { x1: pos, x2: pos, y1: m.top, y2: m.top + ph, stroke: css("--ref"), "stroke-width": 1,
        "stroke-dasharray": r.dash ? "3 3" : null }, svg);
      if (r.label) txt(svg, pos + 4, m.top + 10 + (r.row || 0) * 13, r.label, { class: "ref-label" });
    }

    // --- полосы интервалов ---
    const okv = (v) => v !== null && v !== undefined && Number.isFinite(v) && (!spec.yLog || v > 0);
    for (const b of spec.bands || []) {
      let seg = [];
      const flush = () => {
        if (seg.length) {
          const up = seg.map((i) => `${xs(i)},${ys(b.hi[i])}`), dn = seg.slice().reverse().map((i) => `${xs(i)},${ys(b.lo[i])}`);
          if (seg.length === 1) { const i = seg[0], w = band * 0.18; up.splice(0, 1, `${xs(i) - w},${ys(b.hi[i])}`, `${xs(i) + w},${ys(b.hi[i])}`);
            dn.splice(0, 1, `${xs(i) + w},${ys(b.lo[i])}`, `${xs(i) - w},${ys(b.lo[i])}`); }
          el("path", { d: `M${up.join("L")}L${dn.join("L")}Z`, fill: css(b.colorVar), "fill-opacity": b.opacity || 0.35, stroke: "none" }, svg);
        }
        seg = [];
      };
      b.lo.forEach((_, i) => { if (okv(b.lo[i]) && okv(b.hi[i])) seg.push(i); else flush(); });
      flush();
    }

    // --- столбцы ---
    const barNodes = [];
    if (spec.bars) {
      const bw = Math.min(24, band * 0.7), base = ys(Math.max(y0, 0));
      spec.bars.values.forEach((v, i) => {
        if (v === null || !Number.isFinite(v)) { barNodes.push(null); return; }
        const y = ys(v);
        barNodes.push(el("path", { d: roundedTopBar(xs(i) - bw / 2, y, bw, base - y, 4), fill: css(spec.bars.colorVar) }, svg));
      });
    }
    // --- сгруппированные столбцы (несколько рядов в одной группе) ---
    const groupNodes = [];
    if (spec.barGroups && spec.barGroups.length) {
      const k = spec.barGroups.length, gap = 2;
      const bw = Math.min(24, (band * 0.8 - gap * (k - 1)) / k);
      const total = bw * k + gap * (k - 1);
      const base = m.top + ph;
      spec.barGroups.forEach((b, bi) => {
        const nodes = [];
        b.values.forEach((v, i) => {
          if (v === null || !Number.isFinite(v) || (spec.yLog && v <= 0)) { nodes.push(null); return; }
          const x = xs(i) - total / 2 + bi * (bw + gap), y = ys(v);
          nodes.push(el("path", { d: roundedTopBar(x, y, bw, base - y, 3), fill: css(b.colorVar) }, svg));
        });
        groupNodes.push(nodes);
      });
    }
    // --- точки (для логарифмической шкалы) ---
    if (spec.points) {
      spec.points.values.forEach((v, i) => {
        if (v === null || !(v > 0 || !spec.yLog)) return;
        el("circle", { cx: xs(i), cy: ys(v), r: 4.5, fill: css(spec.points.colorVar),
          stroke: css("--surface-1"), "stroke-width": 2 }, svg);
      });
    }
    // --- линии ---
    for (const l of spec.lines || []) {
      if (!l.values) continue;
      let d = "", pen = false;
      l.values.forEach((v, i) => {
        if (v === null || !Number.isFinite(v) || (spec.yLog && v <= 0)) { pen = false; return; }
        d += `${pen ? "L" : "M"}${xs(i)},${ys(v)}`; pen = true;
      });
      if (!l.noLine) el("path", { d, fill: "none", stroke: css(l.colorVar), "stroke-width": l.width || 2, "stroke-linejoin": "round",
        "stroke-linecap": "round", "stroke-dasharray": l.dash ? "6 4" : null }, svg);
      if (l.markers || l.noLine) l.values.forEach((v, i) => {
        if (v === null || !Number.isFinite(v) || (spec.yLog && v <= 0)) return;
        const cx = xs(i) + (l.dx || 0) * band;
        if (l.marker === "diamond") el("path", { d: `M${cx},${ys(v) - 5.5}L${cx + 5.5},${ys(v)}L${cx},${ys(v) + 5.5}L${cx - 5.5},${ys(v)}Z`,
          fill: css(l.colorVar), stroke: css("--surface-1"), "stroke-width": 1.5 }, svg);
        else el("circle", { cx, cy: ys(v), r: l.noLine ? 4.5 : 4, fill: css(l.colorVar), stroke: css("--surface-1"), "stroke-width": 2 }, svg);
      });
    }
    // --- отрезки интервалов с точкой ---
    for (const iv of spec.intervals || []) {
      const color = css(iv.colorVar);
      iv.mid.forEach((v, i) => {
        const cx = xs(i) + (iv.dx || 0) * band;
        if (okv(iv.lo[i]) && okv(iv.hi[i])) {
          el("line", { x1: cx, x2: cx, y1: ys(iv.lo[i]), y2: ys(iv.hi[i]), stroke: color, "stroke-width": 2, "stroke-linecap": "round" }, svg);
          for (const yv of [iv.lo[i], iv.hi[i]]) el("line", { x1: cx - 4, x2: cx + 4, y1: ys(yv), y2: ys(yv), stroke: color, "stroke-width": 1.5 }, svg);
        }
        if (okv(v)) el("circle", { cx, cy: ys(v), r: 4, fill: color, stroke: css("--surface-1"), "stroke-width": 2 }, svg);
      });
    }

    // --- интерактив: вертикальная линия + подсказка со всеми рядами ---
    const hair = el("line", { y1: m.top, y2: m.top + ph, stroke: css("--text-muted"), "stroke-width": 1, visibility: "hidden" }, svg);
    const hit = el("rect", { x: m.left, y: m.top, width: pw, height: ph, fill: "transparent" }, svg);
    let lastBar = null;
    hit.addEventListener("pointermove", (evt) => {
      const rect = svg.getBoundingClientRect();
      const px = (evt.clientX - rect.left) * (W / rect.width);
      const i = Math.max(0, Math.min(n - 1, Math.floor((px - m.left) / band)));
      hair.setAttribute("x1", xs(i)); hair.setAttribute("x2", xs(i)); hair.setAttribute("visibility", "visible");
      if (lastBar) lastBar.setAttribute("fill", css(spec.bars.colorVar));
      if (barNodes[i]) { barNodes[i].setAttribute("fill", css(spec.bars.hoverVar || spec.bars.colorVar)); lastBar = barNodes[i]; }
      groupNodes.forEach((nodes) => nodes.forEach((nd, j) => nd && nd.setAttribute("opacity", j === i ? 1 : 0.55)));
      const rows = [];
      for (const b of spec.bands || []) if (b.name && b.lo[i] !== null && b.lo[i] !== undefined)
        rows.push({ label: b.name, value: `${fmt(b.lo[i])} – ${fmt(b.hi[i])}`, color: css(b.colorVar) });
      if (spec.bars) rows.push({ label: spec.bars.name, value: fmt(spec.bars.values[i]), color: css(spec.bars.colorVar) });
      if (spec.points) rows.push({ label: spec.points.name, value: fmt(spec.points.values[i]), color: css(spec.points.colorVar) });
      for (const b of spec.barGroups || []) rows.push({ label: b.name, value: fmt(b.values[i]), color: css(b.colorVar) });
      for (const l of spec.lines || []) if (l.values && l.values.some((v) => v !== null))
        rows.push({ label: l.name, value: fmt(l.values[i]), color: css(l.colorVar), dash: l.dash });
      for (const iv of spec.intervals || []) if (iv.name && iv.mid[i] !== null && iv.mid[i] !== undefined)
        rows.push({ label: iv.name, value: `${fmt(iv.mid[i])} (${fmt(iv.lo[i])} – ${fmt(iv.hi[i])})`, color: css(iv.colorVar) });
      if (spec.extraTipRows) rows.push(...spec.extraTipRows(i));
      showTip(evt, spec.tipHead ? spec.tipHead(spec.x[i]) : xLabel(spec.x[i]), rows);
    });
    hit.addEventListener("pointerleave", () => {
      hair.setAttribute("visibility", "hidden"); hideTip();
      if (lastBar) { lastBar.setAttribute("fill", css(spec.bars.colorVar)); lastBar = null; }
      groupNodes.forEach((nodes) => nodes.forEach((nd) => nd && nd.setAttribute("opacity", 1)));
    });

    // --- отдельные точки (оценки по ловам) поверх области подсказки: у каждой своя подсказка ---
    (spec.dots || []).forEach((d, di) => {
      const color = css(d.colorVar);
      const nd = spec.dots.length;
      d.points.forEach((p, k) => {
        if (p.y === null || !Number.isFinite(p.y) || (spec.yLog && p.y <= 0)) return;
        // детерминированный разброс внутри своей половины полосы
        const jitter = (((k * 97) % 100) / 100 - 0.5) * band * 0.32;
        const cx = xs(p.i) + (nd > 1 ? (di - (nd - 1) / 2) * band * 0.36 : 0) + jitter, cy = ys(p.y);
        const dot = el("circle", { cx, cy, r: 3.5, fill: color, "fill-opacity": 0.7,
          stroke: css("--surface-1"), "stroke-width": 1 }, svg);
        const hitDot = el("circle", { cx, cy, r: 8, fill: "transparent" }, svg);
        hitDot.addEventListener("pointermove", (evt) => {
          evt.stopPropagation();
          dot.setAttribute("r", 5.5); dot.setAttribute("fill-opacity", 1);
          showTip(evt, p.label || "", [{ label: d.name, value: fmt(p.y), color }]);
        });
        hitDot.addEventListener("pointerleave", () => { dot.setAttribute("r", 3.5); dot.setAttribute("fill-opacity", 0.7); hideTip(); });
      });
    });
  }

  /* ======================================================================
   * Тепловая карта. spec: { cols:[...], rows:[...], z:[[...]], domain:[lo,hi],
   *   colLabel, rowLabel, selectedRow, onRowClick(row), format, colTitle }
   * ====================================================================== */
  function heatmap(container, spec) {
    register(container, () => drawHeat(container, spec));
  }

  function hexToRgb(h) { const v = parseInt(h.replace("#", ""), 16); return [(v >> 16) & 255, (v >> 8) & 255, v & 255]; }
  function seqColor(t) {
    const stops = [0, 1, 2, 3, 4, 5, 6].map((k) => hexToRgb(css(`--seq-${k}`)));
    t = Math.max(0, Math.min(1, t)) * (stops.length - 1);
    const i = Math.min(stops.length - 2, Math.floor(t)), f = t - i;
    const c = stops[i].map((a, k) => Math.round(a + (stops[i + 1][k] - a) * f));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }

  function drawHeat(container, spec) {
    container.replaceChildren();
    const fmt = spec.format || fmtAuto;
    const W = container.clientWidth || 600;
    const m = { top: 8, right: 16, bottom: 58, left: 52 };
    const nc = spec.cols.length, nr = spec.rows.length;
    const cw = (W - m.left - m.right) / nc;
    const ch = Math.max(18, Math.min(28, cw * 0.6));
    const H = m.top + ch * nr + m.bottom;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img" }, container);
    container.style.height = `${H}px`;
    const [lo, hi] = spec.domain;
    const gap = 2;

    spec.rows.forEach((row, r) => {
      const y = m.top + r * ch;
      const selected = spec.selectedRow === row;
      const label = txt(svg, m.left - 8, y + ch / 2 + 4, spec.rowLabel ? spec.rowLabel(row) : String(row),
        { "text-anchor": "end", "font-weight": selected ? 700 : null });
      if (selected) label.style.fill = css("--text-primary");
      spec.cols.forEach((col, c) => {
        const v = spec.z[r][c];
        const x = m.left + c * cw;
        const cell = el("rect", {
          x: x + gap / 2, y: y + gap / 2, width: Math.max(1, cw - gap), height: ch - gap, rx: 2,
          fill: v === null || v === undefined ? css("--surface-2") : seqColor((v - lo) / (hi - lo)),
        }, svg);
        cell.style.cursor = spec.onRowClick ? "pointer" : "default";
        cell.addEventListener("pointermove", (evt) => {
          cell.setAttribute("stroke", css("--text-primary")); cell.setAttribute("stroke-width", 1.5);
          showTip(evt, `${spec.rowLabel ? spec.rowLabel(row) : row}, ${spec.colLabel ? spec.colLabel(col) : col}`,
            [{ label: spec.valueName || "значение", value: v === null || v === undefined ? "нет (старше m1)" : fmt(v) }]);
        });
        cell.addEventListener("pointerleave", () => { cell.removeAttribute("stroke"); hideTip(); });
        if (spec.onRowClick) cell.addEventListener("click", () => spec.onRowClick(row));
      });
      if (selected) el("rect", { x: m.left, y: y + 0.5, width: cw * nc, height: ch - 1, fill: "none",
        stroke: css("--text-primary"), "stroke-width": 1.5, rx: 3 }, svg);
    });

    // подписи столбцов
    const every = Math.ceil((spec.colTick ? 34 : 22) / cw);
    spec.cols.forEach((col, c) => {
      if (c % every === 0) txt(svg, m.left + c * cw + cw / 2, m.top + nr * ch + 14,
        spec.colTick ? spec.colTick(col) : String(col), { "text-anchor": "middle" });
    });
    if (spec.colTitle) txt(svg, m.left + (cw * nc) / 2, m.top + nr * ch + 30, spec.colTitle, { "text-anchor": "middle", class: "axis-title" });

    // шкала цвета
    const lw = Math.min(220, W - m.left - m.right), lx = m.left, ly = H - 16;
    const gid = `grad-${Math.random().toString(36).slice(2)}`;
    const defs = el("defs", {}, svg);
    const grad = el("linearGradient", { id: gid, x1: 0, x2: 1, y1: 0, y2: 0 }, defs);
    for (let k = 0; k <= 6; k++) el("stop", { offset: `${(k / 6) * 100}%`, "stop-color": css(`--seq-${k}`) }, grad);
    el("rect", { x: lx + 34, y: ly - 8, width: lw - 68, height: 8, rx: 2, fill: `url(#${gid})` }, svg);
    txt(svg, lx + 30, ly, fmt(lo), { "text-anchor": "end" });
    txt(svg, lx + lw - 30, ly, fmt(hi), { "text-anchor": "start" });
  }

  return { xy, heatmap, fmtAuto, nf };
})();
