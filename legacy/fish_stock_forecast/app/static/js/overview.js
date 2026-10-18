/* Страница «Обзор» */
(() => {
  const { f0, f3, cap } = UI;
  const $ = (id) => document.getElementById(id);
  const pieces = (v) => {
    if (v === null || v === undefined || !Number.isFinite(v)) return "—";
    const a = Math.abs(v);
    if (a >= 1e9) return `${Charts.nf(1).format(v / 1e9)} млрд`;
    if (a >= 1e6) return `${Charts.nf(a >= 1e8 ? 0 : a >= 1e7 ? 1 : 2).format(v / 1e6)} млн`;
    if (a >= 1e3) return `${Charts.nf(a >= 1e5 ? 0 : 1).format(v / 1e3)} тыс`;
    return f0(v);
  };
  const tonnes = (v) => (v === null || v === undefined || !Number.isFinite(v) ? "—"
    : Charts.nf(Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 1 ? 1 : 2).format(v));
  const pct = (v) => (v === null || v === undefined ? "—" : `${Charts.nf(0).format(v * 100)} %`);
  const dt = (iso) => (iso ? new Date(iso).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" }) : "—");

  // маленький график ряда по годам
  function sparkline(values) {
    const NS = "http://www.w3.org/2000/svg", W = 96, H = 26, pad = 3;
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("width", W); svg.setAttribute("height", H); svg.setAttribute("class", "spark");
    const v = values.map((x) => (x === null ? null : x));
    const ok = v.filter((x) => x !== null);
    if (ok.length < 2) return svg;
    const lo = Math.min(...ok), hi = Math.max(...ok), n = v.length;
    const xs = (i) => pad + (i / (n - 1)) * (W - 2 * pad);
    const ys = (y) => H - pad - (hi > lo ? (y - lo) / (hi - lo) : 0.5) * (H - 2 * pad);
    let d = "", pen = false;
    v.forEach((y, i) => { if (y === null) { pen = false; return; } d += `${pen ? "L" : "M"}${xs(i)},${ys(y)}`; pen = true; });
    const color = getComputedStyle(document.documentElement).getPropertyValue("--series-1").trim();
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", d); path.setAttribute("fill", "none"); path.setAttribute("stroke", color); path.setAttribute("stroke-width", "1.6");
    svg.appendChild(path);
    const last = [...v.keys()].reverse().find((i) => v[i] !== null);
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("cx", xs(last)); c.setAttribute("cy", ys(v[last])); c.setAttribute("r", 2.5); c.setAttribute("fill", color);
    svg.appendChild(c);
    return svg;
  }

  function renderSteps(d) {
    const box = $("steps"); box.replaceChildren();
    for (const s of d.steps) {
      const a = document.createElement("a"); a.className = "step-card"; a.href = s.href;
      const top = document.createElement("div"); top.className = "top";
      const n = document.createElement("span"); n.className = "side-num" + (s.ok ? " ok" : s.partial ? " partial" : ""); n.textContent = s.ok ? "✓" : s.num;
      top.append(n, document.createTextNode(`${s.num}. ${s.title}`));
      const st = document.createElement("div"); st.className = "st"; st.textContent = s.status;
      a.append(top, st); box.appendChild(a);
    }
  }

  function renderTable(d) {
    const yl = d.last_year, fy = d.forecast_years;
    $("table-title").textContent = `Виды рыб, ${yl}`;
    $("table-sub").textContent = fy
      ? `Прогноз: ПДУ ${fy[0]} по F = k·M (k = ${Charts.nf(2).format(d.k)}) и численность ${fy[1]}; «—» — для вида нет расчёта байесовской модели.`
      : "Прогноз появится после расчёта байесовской модели.";
    const t = $("species-table"); t.replaceChildren();
    const cols = ["Вид", `Запас ${d.years[0]}–${yl}`, "Запас по уловам", "Промысловая биомасса, т",
      "ПДУ НПЦ, т", "Байесовская модель", fy ? `ПДУ ${fy[0]}, F = k·M, т` : "ПДУ, F = k·M", fy ? `Численность ${fy[1]}` : "Численность",
      "Вероятность снижения"];
    UI.head(t, cols, ["Байесовская модель"]);
    t.querySelectorAll("th")[1].style.textAlign = "left";
    const tb = document.createElement("tbody");
    for (const r of d.rows) {
      const tr = document.createElement("tr");
      const td0 = document.createElement("td");
      const nm = document.createElement("div"); nm.className = "sp-name"; nm.textContent = cap(r.species);
      const ln = document.createElement("div"); ln.className = "links";
      for (const [href, label] of [["/stock", "запас"], ["/pdu", "ПДУ"], ["/bayes", "модель"], ["/forecast", "прогноз"]]) {
        const a = document.createElement("a"); a.href = `${href}?species=${r.token}`; a.textContent = label; ln.appendChild(a);
      }
      td0.append(nm, ln); tr.appendChild(td0);
      const tdS = document.createElement("td"); if (r.stock_series) tdS.appendChild(sparkline(r.stock_series)); tr.appendChild(tdS);
      UI.cell(tr, pieces(r.stock_last));
      UI.cell(tr, tonnes(r.fishable_last_t)); UI.cell(tr, tonnes(r.npc_pdu_last_t));
      UI.cell(tr, r.bayes ? `${dt(r.bayes.finished)} · расходимостей ${f0(r.bayes.divergences)} · R̂ ${r.bayes.rhat ? f3(r.bayes.rhat) : "—"}`
        : "не рассчитана", "bayes-cell");
      const f = r.forecast;
      UI.cell(tr, f ? `${tonnes(f.pdu_next_t[2])} (${tonnes(f.pdu_next_t[0])}–${tonnes(f.pdu_next_t[4])})` : "—");
      UI.cell(tr, f ? pieces(f.total_end.baranov) : "—");
      UI.cell(tr, f ? pct(f.p_decline.baranov) : "—");
      tb.appendChild(tr);
    }
    t.appendChild(tb);
  }

  (async () => {
    try {
      const d = await UI.fetchJSON("/api/overview");
      $("load-state").hidden = true; $("content").hidden = false;
      renderSteps(d); renderTable(d);
    } catch (e) { $("load-state").textContent = `Ошибка загрузки: ${e.message}`; }
  })();
})();
