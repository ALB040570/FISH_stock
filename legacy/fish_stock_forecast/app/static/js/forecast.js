/* Страница «Прогноз и ПДУ» */
(() => {
  const { f0, f2, f3, cap, ageLabel, ageTitle, ageTip, AGE_AXIS } = UI;
  const $ = (id) => document.getElementById(id);
  const state = { st: null, summary: null, res: null, species: null, focus: "baranov", scale: "linear",
    draft: { horizon: null, k: null, areas: {}, mortality: {}, pdu: null } };
  const COLORS = { baranov: "--series-2", fixed: "--series-4", none: "--series-3" };

  // ---------- форматирование ----------
  const pieces = (v) => {
    if (v === null || v === undefined || !Number.isFinite(v)) return "—";
    const a = Math.abs(v);
    if (a >= 1e9) return `${Charts.nf(a >= 1e11 ? 0 : 1).format(v / 1e9)} млрд`;
    if (a >= 1e6) return `${Charts.nf(a >= 1e8 ? 0 : a >= 1e7 ? 1 : 2).format(v / 1e6)} млн`;
    if (a >= 1e3) return `${Charts.nf(a >= 1e5 ? 0 : 1).format(v / 1e3)} тыс`;
    return a >= 1 || a === 0 ? f0(v) : Charts.nf(2).format(v);
  };
  const tonnes = (v) => (v === null || v === undefined || !Number.isFinite(v) ? "—"
    : Charts.nf(Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 1 ? 1 : 2).format(v));
  const pct = (v) => (v === null || v === undefined ? "—" : `${Charts.nf(0).format(v * 100)} %`);
  const range = (lo, hi, f) => `${f(lo)} – ${f(hi)}`;
  const dt = (iso) => (iso ? new Date(iso).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" }) : "—");

  async function post(url, body) {
    const resp = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body) });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `${resp.status}`);
    return data;
  }

  // ---------- загрузка ----------
  async function loadSettings() {
    state.st = await UI.fetchJSON("/api/forecast/settings");
    const sp = state.species || UI.initialSpecies(state.st.species_list, state.st.species_list.find((s) => state.st.species[s].available));
    state.species = sp;
    resetDraft();
  }
  function resetDraft() {
    const st = state.st, sv = st.species[state.species];
    state.draft = { horizon: st.horizon, k: st.k, areas: { ...st.areas }, mortality: { ...(sv.mortality || {}) },
      pdu: sv.pdu_t ?? sv.npc_last };   // по умолчанию — ПДУ последнего года
  }
  async function loadSummary() { state.summary = await UI.fetchJSON("/api/forecast/summary"); }
  async function loadResults() {
    const tok = state.st.species[state.species].token;
    state.res = await UI.fetchJSON(`/api/forecast/results/${tok}`);
  }
  async function init() {
    try {
      await loadSettings();
      await Promise.all([loadSummary(), loadResults()]);
      $("load-state").hidden = true;
      for (const id of ["settings-card", "summary-card", "filters"]) $(id).hidden = false;
      renderAll();
    } catch (e) { $("load-state").textContent = `Ошибка загрузки: ${e.message}`; }
  }
  function renderAll() { renderSettings(); renderSummary(); renderFilters(); renderResults(); }

  // ---------- настройки ----------
  const fcYears = () => Array.from({ length: +state.draft.horizon }, (_, i) => state.st.last_year + 1 + i);

  function renderSettings() {
    const st = state.st, sv = st.species[state.species], d = state.draft;
    const hs = $("horizon"); hs.replaceChildren();
    for (let h = 1; h <= st.max_horizon; h++) {
      const o = document.createElement("option"); o.value = h;
      o.textContent = `${h} (${st.last_year + 1}–${st.last_year + h})`;
      if (h === +d.horizon) o.selected = true; hs.appendChild(o);
    }
    $("k").value = d.k;
    $("pdu-t").value = d.pdu ?? "";
    $("pdu-t").placeholder = sv.npc_last !== null ? String(sv.npc_last) : "";
    $("pdu-label").textContent = `Фиксированный ПДУ — ${state.species}, т`;

    const t = $("fc-table"); t.replaceChildren();
    const years = fcYears();
    const thead = document.createElement("thead"), hr = document.createElement("tr");
    const th0 = document.createElement("th"); th0.className = "text"; th0.textContent = ""; hr.appendChild(th0);
    for (const y of years) { const th = document.createElement("th"); th.textContent = y; hr.appendChild(th); }
    thead.appendChild(hr); t.appendChild(thead);
    const tb = document.createElement("tbody");
    const row = (label, key, placeholder, store) => {
      const tr = document.createElement("tr");
      const td0 = document.createElement("td"); td0.textContent = label; tr.appendChild(td0);
      for (const y of years) {
        const td = document.createElement("td");
        const inp = document.createElement("input"); inp.type = "number"; inp.step = "any"; inp.min = "0";
        inp.className = "num-input cell-input"; inp.inputMode = "decimal";
        inp.value = store[y] ?? store[String(y)] ?? ""; inp.placeholder = placeholder;
        inp.dataset.key = key; inp.dataset.year = y;
        inp.addEventListener("input", () => { if (inp.value === "") delete store[String(y)]; else store[String(y)] = inp.value; });
        td.appendChild(inp); tr.appendChild(td);
      }
      tb.appendChild(tr);
    };
    row("Площадь водоёма, км²", "area", String(st.area_last), d.areas);
    const hint = sv.s_mature_hist !== null && sv.s_mature_hist !== undefined ? `≈ ${f3(sv.s_mature_hist)}` : "из истории";
    row(`Смертность половозрелых — ${state.species}, доля в год`, "mortality", hint, d.mortality);
    t.appendChild(tb);
    $("settings-msg").textContent = "";
  }
  $("horizon").addEventListener("change", (e) => { state.draft.horizon = +e.target.value; renderSettings(); });
  $("k").addEventListener("input", (e) => { state.draft.k = e.target.value; });
  $("pdu-t").addEventListener("input", (e) => { state.draft.pdu = e.target.value === "" ? null : e.target.value; });

  $("btn-save").addEventListener("click", async () => {
    const d = state.draft, years = fcYears().map(String);
    const pick = (o) => Object.fromEntries(Object.entries(o).filter(([y, v]) => years.includes(String(y)) && v !== "" && v !== null));
    const body = { horizon: +d.horizon, k: d.k, areas: pick(d.areas),
      species: { [state.species]: { mortality: pick(d.mortality), pdu_t: d.pdu } } };
    const b = $("btn-save"); b.disabled = true; $("settings-msg").textContent = "Считаю…";
    try {
      state.st = await post("/api/forecast/settings", body);
      resetDraft();
      await Promise.all([loadSummary(), loadResults()]);
      renderAll();
      $("settings-msg").textContent = `Сохранено и пересчитано ${new Date().toLocaleTimeString("ru-RU")}.`;
    } catch (e) { $("settings-msg").textContent = `Не сохранено: ${e.message}`; }
    b.disabled = false;
  });
  $("btn-reset").addEventListener("click", async () => {
    if (!confirm("Сбросить все настройки прогноза (горизонт, k, площади, смертность и фиксированный ПДУ всех видов)?")) return;
    state.st = await post("/api/forecast/settings/reset");
    resetDraft();
    await Promise.all([loadSummary(), loadResults()]);
    renderAll();
    $("settings-msg").textContent = "Настройки сброшены.";
  });

  // ---------- сводка ----------
  function renderSummary() {
    const S = state.summary, t = $("summary-table"); t.replaceChildren();
    const yrs = S.years;
    if (!yrs) { $("summary-sub").textContent = "Нет ни одного нового расчёта байесовской модели — прогноз строить не по чему."; return; }
    const [yl, y1, ye] = yrs;
    $("summary-title").textContent = `Сводка по видам: ПДУ ${y1} и численность ${ye}`;
    $("summary-sub").textContent = `k = ${Charts.nf(2).format(S.k)}. Нажмите на строку, чтобы открыть вид.`;
    UI.head(t, ["Вид", `ПДУ ${y1}, F = k·M, т`, "95 % интервал", `ПДУ НПЦ ${yl}, т`, "F = k·M / НПЦ",
      `Численность ${yl}`, `${ye}: F = k·M`, `${ye}: фикс. ПДУ`, `${ye}: без промысла`, "Вероятность снижения, F = k·M"]);
    const tb = document.createElement("tbody");
    for (const r of S.rows) {
      const tr = document.createElement("tr");
      tr.className = "clickable" + (r.species === state.species ? " selected" : "");
      tr.addEventListener("click", () => selectSpecies(r.species));
      UI.cell(tr, cap(r.species));
      if (!r.available) {
        const td = UI.cell(tr, "нет нового расчёта байесовской модели", "text"); td.colSpan = 9;
      } else {
        const p = r.pdu_next_t;
        UI.cell(tr, tonnes(p[2])); UI.cell(tr, range(p[0], p[4], tonnes)); UI.cell(tr, tonnes(r.npc_last_t));
        UI.cell(tr, r.npc_last_t ? Charts.nf(2).format(p[2] / r.npc_last_t) : "—");
        UI.cell(tr, pieces(r.total_last)); UI.cell(tr, pieces(r.total_end.baranov));
        UI.cell(tr, pieces(r.total_end.fixed)); UI.cell(tr, pieces(r.total_end.none));
        UI.cell(tr, pct(r.p_decline.baranov));
      }
      tb.appendChild(tr);
    }
    t.appendChild(tb);
  }
  async function selectSpecies(sp) {
    state.species = sp; resetDraft();
    await loadResults(); renderAll();
  }

  function renderFilters() {
    UI.segmented($("species-tabs"), state.st.species_list.map((s) => ({ value: s, label: cap(s) + (state.st.species[s].available ? "" : " —") })),
      state.species, (s) => selectSpecies(s));
    UI.segmented($("focus-tabs"), state.st.scenarios.map((s) => ({ value: s, label: state.st.scenario_titles[s] })),
      state.focus, (v) => { state.focus = v; renderFilters(); renderResults(); });
    UI.segmented($("scale-toggle"), [{ value: "linear", label: "Линейная" }, { value: "log", label: "Логарифм." }],
      state.scale, (v) => { state.scale = v; renderFilters(); renderResults(); });
  }

  // ---------- результаты ----------
  function renderResults() {
    const R = state.res;
    if (!R || !R.available) {
      $("content").hidden = true;
      const e = $("empty"); e.hidden = false; e.replaceChildren();
      const h = document.createElement("h2"); h.textContent = `Для вида «${state.species}» нет нового расчёта байесовской модели`;
      const p = document.createElement("p");
      p.textContent = "Прогноз строится по 500 выборкам модели. Рассчитайте вид на странице «Байесовская модель» (кнопка «Рассчитать»), затем вернитесь сюда.";
      e.append(h, p);
      $("footer-info").textContent = "";
      return;
    }
    $("empty").hidden = true; $("content").hidden = false;
    renderTiles(); renderTotal(); renderBiomass(); renderPdu(); renderAges(); renderTable();
    $("footer-info").textContent = `Байесовская модель: расчёт от ${dt(R.finished)}, ${R.n_draws} выборок. Сценарии используют одни и те же случайные условия будущих лет.`;
  }

  // ряды «история + прогноз» на общей оси лет
  function joined(R, histArr, fcArr) {
    const nh = R.years_hist.length;
    return { x: [...R.years_hist, ...R.years_fc], hist: [...histArr, ...R.years_fc.map(() => null)],
      fc: (arr, joinVal) => [...R.years_hist.map((_, i) => (i === nh - 1 ? joinVal : null)), ...arr] };
  }

  function renderTiles() {
    const R = state.res, S = R.scenarios, y1 = R.years_fc[0], ye = R.years_fc[R.years_fc.length - 1], yl = R.years_hist[R.years_hist.length - 1];
    const b = S.baranov.pdu_t_q, F = R.F_q, M = R.Mbar_q;
    const f = S[state.focus];
    $("tiles").replaceChildren(
      UI.tile(`ПДУ ${y1}, F = k·M`, `${tonnes(b[2][0])} т`, `95 %: ${range(b[0][0], b[4][0], tonnes)} т`),
      UI.tile(`ПДУ НПЦ ${yl}`, `${tonnes(R.settings.npc_last)} т`, `фиксированный в прогнозе: ${tonnes(R.settings.pdu_fixed_t)} т`),
      UI.tile(`F ${y1}`, f3(F[2][0]), `M̄ = ${f3(M[2][0])}, k = ${Charts.nf(2).format(R.settings.k)}`),
      UI.tile(`Численность ${yl}`, pieces(R.hist.total_q[2][R.years_hist.length - 1]), "возрасты 1–2 и старше"),
      UI.tile(`Численность ${ye}`, pieces(f.total_q[2][f.total_q[2].length - 1]), state.st.scenario_titles[state.focus]),
      UI.tile("Вероятность снижения", pct(f.p_decline), `${ye} ниже ${yl}, ${state.st.scenario_titles[state.focus]}`),
    );
    const notes = [...(R.notes || [])];
    const setM = R.settings.mortality.map((v, i) => (v === null ? null : `${R.years_fc[i]}: ${f3(v)}`)).filter(Boolean);
    if (setM.length) notes.push(`смертность задана: ${setM.join(", ")}; в остальные годы — из истории`);
    UI.note($("status-note"), notes);
  }

  function scenarioChart(el, R, histQ, fcKey, yTitle, fmt, lastHistQ) {
    const nh = R.years_hist.length;
    const J = joined(R, histQ[2], []);
    const lines = [{ name: "История, медиана", values: J.hist, colorVar: "--series-1", width: 2.5 }];
    const bands = [{ name: "История, 95 %", lo: joined(R, histQ[0]).hist, hi: joined(R, histQ[4]).hist, colorVar: "--series-1", opacity: 0.16 }];
    const lastMed = lastHistQ ? lastHistQ[2] : histQ[2][nh - 1];
    for (const sc of state.st.scenarios) {
      const qd = R.scenarios[sc][fcKey];
      lines.push({ name: state.st.scenario_titles[sc], values: J.fc(qd[2], lastMed), colorVar: COLORS[sc], markers: sc === state.focus });
    }
    const fq = R.scenarios[state.focus][fcKey];
    const jl = (k) => J.fc(fq[k], lastHistQ ? lastHistQ[k] : histQ[k][nh - 1]);
    bands.push({ name: null, lo: jl(0), hi: jl(4), colorVar: COLORS[state.focus], opacity: 0.14 });
    bands.push({ name: null, lo: jl(1), hi: jl(3), colorVar: COLORS[state.focus], opacity: 0.28 });
    Charts.xy(el, { x: J.x, xTitle: "Год", yTitle, yLog: state.scale === "log", format: fmt, bands, lines,
      vrefs: [{ x: R.years_hist[nh - 1] + 0.5, label: "прогноз →", dash: true }] });
  }

  function renderTotal() {
    const R = state.res;
    $("total-title").textContent = `Численность — ${state.species}`;
    scenarioChart($("chart-total"), R, R.hist.total_q, "total_q", "штук", pieces, R.hist.total_last_draws_q);
  }
  function renderBiomass() {
    const R = state.res;
    scenarioChart($("chart-biomass"), R, R.hist.fishable_q, "fishable_q", "тонн", tonnes, null);
  }
  function renderPdu() {
    const R = state.res, nh = R.years_hist.length;
    const J = joined(R, R.hist.npc_pdu_t, []);
    const b = R.scenarios.baranov.pdu_t_q, fx = R.scenarios.fixed.pdu_t_q;
    const last = R.hist.npc_pdu_t[nh - 1];
    Charts.xy($("chart-pdu"), {
      x: J.x, xTitle: "Год", yTitle: "тонн", format: tonnes, yLog: state.scale === "log",
      bands: [{ name: "F = k·M, 95 %", lo: J.fc(b[0], null), hi: J.fc(b[4], null), colorVar: "--series-2", opacity: 0.16 },
        { name: null, lo: J.fc(b[1], null), hi: J.fc(b[3], null), colorVar: "--series-2", opacity: 0.3 }],
      lines: [
        { name: "ПДУ НПЦ (история)", values: J.hist, colorVar: "--series-4", markers: true },
        { name: "F = k·M, медиана", values: J.fc(b[2], null), colorVar: "--series-2", markers: true },
        { name: "Фиксированный ПДУ", values: J.fc(fx[2], last), colorVar: "--series-4", dash: true },
      ],
      vrefs: [{ x: R.years_hist[nh - 1] + 0.5, label: "прогноз →", dash: true }],
    });
  }
  function renderAges() {
    const R = state.res, yl = R.years_hist[R.years_hist.length - 1], ye = R.years_fc[R.years_fc.length - 1];
    $("ages-title").textContent = `Возрастная структура: ${yl} и ${ye}`;
    Charts.xy($("chart-ages"), {
      x: R.ages, xLabel: ageLabel, xTitle: AGE_AXIS, yTitle: "штук", yLog: true, format: pieces, tipHead: ageTip,
      barGroups: [
        { name: `${yl} (модель)`, values: R.hist.X_last_q[2], colorVar: "--series-1" },
        { name: `${ye}: ${state.st.scenario_titles[state.focus]}`, values: R.scenarios[state.focus].X_last_q[2], colorVar: COLORS[state.focus] },
      ],
      vrefs: [{ x: R.m0 - 0.5, label: "промысловые →", dash: true }],
    });
    const med = R.scenarios.baranov.pdu_pcs_median;
    const idx = R.ages.map((a, i) => (a >= R.m0 ? i : -1)).filter((i) => i >= 0);
    const palette = ["--series-2", "--series-3", "--series-4", "--series-1"];
    const pick = [0, med.length - 1].filter((v, i, a) => a.indexOf(v) === i);
    $("pdu-ages-title").textContent = `ПДУ по возрастам, F = k·M: ${pick.map((h) => R.years_fc[h]).join(" и ")}`;
    Charts.xy($("chart-pdu-ages"), {
      x: idx.map((i) => R.ages[i]), xLabel: ageLabel, xTitle: AGE_AXIS, yTitle: "штук", format: pieces, tipHead: ageTip,
      barGroups: pick.map((h, n) => ({ name: String(R.years_fc[h]), values: idx.map((i) => med[h][i]), colorVar: palette[n] })),
    });
  }
  function renderTable() {
    const R = state.res, sc = state.focus, S = R.scenarios[sc];
    $("table-title").textContent = `По годам прогноза — ${state.st.scenario_titles[sc]}`;
    const t = $("years-table"); t.replaceChildren();
    const cols = ["Год", "Площадь, км²", "s половозрелых", "β", "Численность", "95 % интервал", "Промысловая биомасса, т", "ПДУ, т", "ПДУ 95 %", "ПДУ, штук", "Изъятие β·ПДУ, т"];
    if (sc === "baranov") cols.push("F", "M̄");
    UI.head(t, cols);
    const tb = document.createElement("tbody");
    R.years_fc.forEach((y, h) => {
      const tr = document.createElement("tr");
      UI.cell(tr, y); UI.cell(tr, tonnes(R.settings.areas[h]) + (R.settings.area_default_years.includes(y) ? " *" : ""));
      UI.cell(tr, f3(R.s_mature_q[2][h]) + (R.settings.mortality[h] === null ? "" : " (задана)"));
      UI.cell(tr, f2(R.beta_q[2][h]));
      UI.cell(tr, pieces(S.total_q[2][h])); UI.cell(tr, range(S.total_q[0][h], S.total_q[4][h], pieces));
      UI.cell(tr, tonnes(S.fishable_q[2][h])); UI.cell(tr, tonnes(S.pdu_t_q[2][h]));
      UI.cell(tr, sc === "none" ? "—" : range(S.pdu_t_q[0][h], S.pdu_t_q[4][h], tonnes));
      UI.cell(tr, pieces(S.pdu_pcs_total_q[2][h])); UI.cell(tr, tonnes(S.removal_t_q[2][h]));
      if (sc === "baranov") { UI.cell(tr, f3(R.F_q[2][h])); UI.cell(tr, f3(R.Mbar_q[2][h])); }
      tb.appendChild(tr);
    });
    t.appendChild(tb);
  }

  init();
})();
