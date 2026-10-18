/* Страница «Байесовская модель» */
(() => {
  const { f0, f2, f3, cap, ageLabel, ageTitle, ageTip, AGE_AXIS } = UI;
  const $ = (id) => document.getElementById(id);
  const state = {
    ov: null, species: null, source: null, res: null, year: null,
    scale: "log", ages: "obs", dataMode: "raw", job: null, pollTimer: null, lastJobState: null,
    expanded: new Set(),
  };
  const SOURCES = [
    { value: "new", label: "Новый расчёт" },
    { value: "prior", label: "Априорная проверка" },
    { value: "check", label: "Сверка со старым скриптом" },
  ];
  const PHASES = { start: "запуск", inputs: "подготовка данных", compile: "сборка модели и первые шаги",
    tune: "настройка (tune)", draws: "выборка", save: "сохранение результатов", done: "готово",
    cancelled: "остановлено", failed: "ошибка" };

  // ---------- форматирование ----------
  const pieces = (v) => {
    if (v === null || v === undefined || !Number.isFinite(v)) return "—";
    const a = Math.abs(v);
    if (a >= 1e9) return `${Charts.nf(a >= 1e11 ? 0 : 1).format(v / 1e9)} млрд`;
    if (a >= 1e6) return `${Charts.nf(a >= 1e8 ? 0 : a >= 1e7 ? 1 : 2).format(v / 1e6)} млн`;
    if (a >= 1e3) return `${Charts.nf(a >= 1e5 ? 0 : 1).format(v / 1e3)} тыс`;
    return a >= 1 || a === 0 ? f0(v) : Charts.nf(2).format(v);
  };
  const fixed2 = (v) => (v === null || v === undefined || !Number.isFinite(v) ? "—"
    : new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v));
  const num = (v) => {
    if (v === null || v === undefined || !Number.isFinite(v)) return "—";
    const a = Math.abs(v);
    if (a >= 1e4) return pieces(v);
    return Charts.nf(a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : a >= 0.01 ? 3 : 5).format(v);
  };
  const hms = (sec) => {
    if (sec === null || sec === undefined || !Number.isFinite(sec)) return "—";
    sec = Math.round(sec);
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    return h ? `${h} ч ${String(m).padStart(2, "0")} мин` : m ? `${m} мин ${String(s).padStart(2, "0")} с` : `${s} с`;
  };
  const dt = (iso) => (iso ? new Date(iso).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" }) : "—");
  const col = (m, k) => m.map((r) => (r ? r[k] : null));          // столбец k матрицы
  const row = (q, k) => q[k];                                      // квантиль k: 0 — 2,5 %, 1 — 25 %, 2 — медиана, 3 — 75 %, 4 — 97,5 %

  async function post(url, body) {
    const resp = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body) });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `${resp.status}`);
    return data;
  }

  // ---------- загрузка ----------
  async function loadOverview() {
    state.ov = await UI.fetchJSON("/api/bayes/overview");
    state.species = state.species || UI.initialSpecies(state.ov.species_list);
    state.job = state.ov.job;
  }
  function pickSource() {
    const r = state.ov.species[state.species].results;
    if (state.source) return state.source;                 // выбран на странице — показываем, даже если расчёта нет
    return ["new", "check", "prior"].find((s) => r[s]) || "new";
  }
  async function loadResults() {
    state.source = pickSource();
    const tok = state.ov.species[state.species].token;
    state.res = await UI.fetchJSON(`/api/bayes/results/${tok}?source=${state.source}`);
    if (state.res.available && (!state.year || !state.res.years.includes(state.year)))
      state.year = state.res.years[state.res.years.length - 1];
  }
  async function init() {
    try {
      await loadOverview();
      await loadResults();
      $("load-state").hidden = true;
      $("run-card").hidden = false; $("settings-card").hidden = false;
      renderAll();
      if (state.job && state.job.state === "running") startPolling();
    } catch (e) {
      $("load-state").textContent = `Ошибка загрузки: ${e.message}`;
    }
  }

  function renderAll() {
    buildFilters(); renderRun(); renderSettings(); renderResults();
  }

  function buildFilters() {
    const ov = state.ov;
    UI.segmented($("species-tabs"), ov.species_list.map((s) => ({ value: s, label: cap(s) })), state.species, async (s) => {
      state.species = s; state.source = null; await loadResults(); renderAll();
    });
    const r = ov.species[state.species].results;
    UI.segmented($("source-tabs"), SOURCES.map((s) => ({ value: s.value, label: s.label + (r[s.value] ? "" : " —") })),
      state.source, async (v) => { state.source = v; await loadResults(); renderAll(); });
    const tok = ov.species[state.species].token;
    $("excel-link").href = `/api/bayes/export.xlsx?species=${tok}&source=${state.source}`;
    $("excel-link").hidden = !state.res || !state.res.available;
  }

  // ---------- запуск и ход расчёта ----------
  function running() { return state.job && state.job.state === "running"; }

  function renderRun() {
    const sp = state.species, job = state.job;
    $("btn-run").textContent = `Рассчитать: ${sp}`;
    const busy = running();
    for (const id of ["btn-run", "btn-run-all", "btn-check"]) $(id).disabled = busy;
    $("btn-cancel").hidden = !busy;
    const info = state.ov.species[sp].results.new;
    let title = "Расчёт", sub = "";
    if (busy) {
      const i = job.index || 0, n = job.species.length;
      title = `Идёт расчёт${job.mode === "check" ? " (сверка)" : ""}: ${job.current || job.species[0]}` + (n > 1 ? ` — вид ${i + 1} из ${n}` : "");
      sub = `Запущен ${dt(job.started)}. Страницу можно закрыть: расчёт идёт в отдельном процессе.`;
    } else if (job && job.state && job.state !== "none") {
      const done = (job.finished || []).filter((f) => !f.error).map((f) => f.species);
      const failed = (job.finished || []).filter((f) => f.error);
      const what = `${job.mode === "check" ? "сверка" : "расчёт"} (${(job.species || []).join(", ")})`;
      title = { done: `Последний ${what} завершён`, failed: `Последний ${what} завершился с ошибкой`,
        cancelled: `Последний ${what} остановлен` }[job.state] || "Расчёт";
      sub = `${dt(job.started)} – ${dt(job.ended)}` + (done.length ? `; готово: ${done.join(", ")}` : "")
        + (failed.length ? `; ошибки: ${failed.map((f) => `${f.species} — ${f.error}`).join("; ")}` : "")
        + (job.error && !failed.length ? `. ${job.error}` : "");
    } else {
      sub = info ? `Новый расчёт вида: ${dt(info.finished)}, ${hms(info.seconds)}.` : "Для этого вида новый расчёт ещё не выполнялся. Один вид считается от 15 минут до 2 часов.";
    }
    $("run-title").textContent = title; $("run-sub").textContent = sub;

    const notes = [];
    if (!state.ov.pymc) notes.push("PyMC не найден в окружении сервера — выборка NUTS не запустится (pip install pymc); априорная проверка работает и без него");
    if (!busy && job && job.state === "failed" && job.log && job.log.length) notes.push("подробности — в журнале ниже");
    UI.note($("run-note"), notes);

    // ход расчёта
    const pr = busy ? job.progress || {} : null;
    $("progress").hidden = !busy;
    if (busy) {
      const chains = pr.chains || {};
      const total = pr.total || 0;
      const keys = Object.keys(chains);
      const doneSteps = keys.reduce((a, k) => a + chains[k], 0);
      const frac = total && keys.length ? doneSteps / (total * keys.length) : 0;
      const elapsed = job.species_started_ts ? (job.now_ts - job.species_started_ts) : null;
      const eta = pr.sampling_seconds && frac > 0.02 ? pr.sampling_seconds * (1 - frac) / frac : null;
      const cfg = state.ov.species[job.current || sp];
      const meta = [
        ["Этап", PHASES[pr.phase] || pr.phase || "—"],
        ["Прошло", hms(elapsed)],
        ["Выполнено", total ? `${Charts.nf(0).format(frac * 100)} %` : "—"],
        ["Осталось", eta ? `≈ ${hms(eta)}` : "—"],
        ["Расходимостей", pr.divergences ?? "—"],
      ];
      $("progress-meta").replaceChildren(...meta.map(([k, v]) => { const s = document.createElement("span");
        s.append(`${k}: `); const b = document.createElement("b"); b.textContent = v; s.appendChild(b); return s; }));
      const bars = $("chain-bars"); bars.replaceChildren();
      const tune = cfg ? (job.mode === "check" ? cfg.defaults.script_tune : cfg.current.tune) : 0;
      for (const k of keys) {
        const r = document.createElement("div"); r.className = "chain-bar";
        const l = document.createElement("span"); l.textContent = `цепь ${+k + 1}`;
        const tr = document.createElement("div"); tr.className = "track";
        const fill = document.createElement("div"); fill.className = "fill"; fill.style.width = `${Math.min(100, (chains[k] / total) * 100)}%`;
        tr.appendChild(fill);
        if (tune && total) { const t = document.createElement("div"); t.className = "tune"; t.style.left = `${(tune / total) * 100}%`; t.title = "конец настройки"; tr.appendChild(t); }
        const c = document.createElement("span"); c.textContent = `${chains[k]} / ${total}`;
        r.append(l, tr, c); bars.appendChild(r);
      }
      if (!keys.length) { const p = document.createElement("p"); p.className = "muted small";
        p.textContent = pr.phase === "compile" ? "PyTensor собирает модель — обычно 1–3 минуты." : "Подготовка…"; bars.appendChild(p); }
    }
    const log = job && job.log && job.log.length ? job.log : null;
    $("log-box").hidden = !log;
    if (log) $("log").textContent = log.join("\n");
  }

  async function startJob(species, mode) {
    try {
      state.job = await post("/api/bayes/run", { species, mode });
      renderRun(); startPolling();
    } catch (e) { UI.note($("run-note"), [e.message]); }
  }
  $("btn-run").addEventListener("click", () => startJob([state.ov.species[state.species].token], "new"));
  $("btn-run-all").addEventListener("click", () => {
    if (confirm(`Рассчитать все ${state.ov.species_list.length} видов подряд? Это может занять несколько часов.`))
      startJob(state.ov.species_list.map((s) => state.ov.species[s].token), "new");
  });
  $("btn-check").addEventListener("click", () => startJob([state.ov.species[state.species].token], "check"));
  $("btn-cancel").addEventListener("click", async () => {
    if (!confirm("Остановить расчёт? Результаты текущего вида не сохранятся.")) return;
    state.job = await post("/api/bayes/cancel"); renderRun();
  });
  $("btn-prior").addEventListener("click", async () => {
    const b = $("btn-prior"); b.disabled = true; b.textContent = "Считаю…";
    try {
      state.res = await post(`/api/bayes/prior/${state.ov.species[state.species].token}`);
      state.source = "prior";
      await loadOverview();
      renderAll();
    } catch (e) { UI.note($("run-note"), [e.message]); }
    b.disabled = false; b.textContent = "Априорная проверка";
  });

  function startPolling() {
    if (state.pollTimer) return;
    state.lastJobState = state.job && state.job.state;
    let finishedCount = (state.job && state.job.finished || []).length;
    state.pollTimer = setInterval(async () => {
      try {
        const job = await UI.fetchJSON("/api/bayes/status");
        state.job = job;
        const n = (job.finished || []).length;
        if (n !== finishedCount || job.state !== "running") {
          finishedCount = n;
          await loadOverview(); await loadResults(); renderAll();
        } else renderRun();
        if (job.state !== "running") { clearInterval(state.pollTimer); state.pollTimer = null; }
      } catch (e) { /* сервер перезапускается — попробуем позже */ }
    }, 2000);
  }

  // ---------- настройки ----------
  function renderSettings() {
    const sp = state.species, info = state.ov.species[sp];
    const form = $("settings-form"); form.replaceChildren();
    const groups = new Map();
    for (const f of state.ov.schema) { if (!groups.has(f.group)) groups.set(f.group, []); groups.get(f.group).push(f); }
    let changed = 0;
    for (const [g, list] of groups) {
      const fs = document.createElement("fieldset");
      const lg = document.createElement("legend"); lg.textContent = g; fs.appendChild(lg);
      for (const f of list) {
        const cur = info.current[f.key], def = info.defaults[f.key];
        const isChanged = cur !== def;
        if (isChanged) changed++;
        const r = document.createElement("div"); r.className = "set-row" + (isChanged ? " changed" : "") + (f.type === "select" ? " wide" : "");
        const id = `f-${f.key}`;
        const lab = document.createElement("label"); lab.htmlFor = id; lab.textContent = f.label;
        let inp;
        if (f.type === "select") {
          inp = document.createElement("select");
          for (const o of f.options) { const op = document.createElement("option"); op.value = o.value; op.textContent = o.label;
            if (o.value === cur) op.selected = true; inp.appendChild(op); }
        } else if (f.type === "bool") {
          inp = document.createElement("input"); inp.type = "checkbox"; inp.checked = !!cur;
        } else {
          inp = document.createElement("input"); inp.type = "number"; inp.step = f.type === "int" ? "1" : "any";
          inp.value = cur; inp.inputMode = f.type === "int" ? "numeric" : "decimal";
        }
        inp.id = id; inp.dataset.key = f.key; inp.dataset.type = f.type;
        r.append(lab, inp);
        if (isChanged) {
          const d = document.createElement("div"); d.className = "default";
          const dv = f.type === "select" ? (f.options.find((o) => o.value === def) || {}).label || def : f.type === "bool" ? (def ? "да" : "нет") : def;
          d.textContent = `в скрипте: ${dv}`; r.appendChild(d);
        }
        fs.appendChild(r);
      }
      form.appendChild(fs);
    }
    $("settings-title").textContent = `Настройки модели: ${sp}`;
    $("settings-sub").textContent = changed ? `· изменено ${changed} из ${state.ov.schema.length}` : "· как в скрипте " + (info.defaults.old_flag || "");
    $("settings-msg").textContent = "";
  }
  function formValues() {
    const out = {};
    for (const inp of $("settings-form").querySelectorAll("[data-key]")) {
      const t = inp.dataset.type;
      out[inp.dataset.key] = t === "bool" ? inp.checked : t === "select" ? inp.value : inp.value === "" ? null : Number(inp.value);
    }
    return out;
  }
  $("btn-save").addEventListener("click", async () => {
    const tok = state.ov.species[state.species].token;
    const vals = formValues();
    if (Object.values(vals).some((v) => v === null || Number.isNaN(v))) { $("settings-msg").textContent = "Заполните все поля числами."; return; }
    try {
      const r = await post(`/api/bayes/config/${tok}`, vals);
      Object.assign(state.ov.species[state.species], { current: r.current, overrides: r.overrides });
      renderSettings(); await loadResults(); renderResults(); buildFilters();
      $("settings-msg").textContent = `Сохранено ${new Date().toLocaleTimeString("ru-RU")}. Действует на следующий расчёт.`;
    } catch (e) { $("settings-msg").textContent = `Не сохранено: ${e.message}`; }
  });
  $("btn-reset").addEventListener("click", async () => {
    if (!confirm(`Вернуть для вида «${state.species}» значения из скрипта?`)) return;
    const r = await post(`/api/bayes/config/${state.ov.species[state.species].token}/reset`);
    Object.assign(state.ov.species[state.species], { current: r.current, overrides: r.overrides });
    renderSettings(); await loadResults(); renderResults();
    $("settings-msg").textContent = "Возвращены значения скрипта.";
  });

  // ---------- результаты ----------
  function renderResults() {
    const R = state.res;
    buildFilters();
    if (!R || !R.available) {
      $("content").hidden = true;
      const e = $("empty"); e.hidden = false; e.replaceChildren();
      const h = document.createElement("h2");
      const p = document.createElement("p");
      h.textContent = `Для вида «${state.species}» ещё нет результата «${SOURCES.find((s) => s.value === state.source).label}»`;
      p.textContent = state.source === "prior"
        ? "Нажмите «Априорная проверка» — это займёт несколько секунд."
        : state.source === "check"
          ? "«Сверка со старым скриптом» пересчитывает модель на входных данных старого проекта и сравнивает результат со старым файлом из data_stock."
          : "Нажмите «Рассчитать» (15 минут – 2 часа) или сначала «Априорная проверка», чтобы убедиться, что априорные распределения согласуются с данными.";
      e.append(h, p);
      $("footer-info").textContent = `Папка результатов: ${state.ov.results_dir}`;
      return;
    }
    $("empty").hidden = true; $("content").hidden = false;
    UI.yearSelect($("year-select"), R.years, state.year);
    UI.segmented($("scale-toggle"), [{ value: "log", label: "Логарифм." }, { value: "linear", label: "Линейная" }],
      state.scale, (v) => { state.scale = v; renderResults(); });
    UI.segmented($("ages-toggle"), [{ value: "obs", label: "1–2 и старше" }, { value: "all", label: "с сеголетками" }],
      state.ages, (v) => { state.ages = v; renderResults(); });
    UI.segmented($("data-toggle"), [{ value: "raw", label: "оценки как есть" }, { value: "q", label: "оценки / q" }],
      state.dataMode, (v) => { state.dataMode = v; renderResults(); });
    renderTiles(); renderTotal(); renderAges(); renderRecruits(); renderCurves(); renderBetaQ(); renderDeaths();
    renderParams(); renderDiag();
    const m = R.meta;
    $("footer-info").textContent = [`Файл: ${R.file}`, `${m.mode_title}: ${dt(m.finished)}`,
      `ловов в правдоподобии: ${m.n_obs}`, `папка результатов: ${state.ov.results_dir}`].join(" · ");
  }
  $("year-select").addEventListener("change", (e) => { state.year = +e.target.value; renderResults(); });

  const yi = () => state.res.years.indexOf(state.year);
  const qAge = (j) => { const q = state.res.q_bias_q[2][j - 1]; return q > 0 ? q : 1; };
  const dataTotal = (byAge) => byAge.map((r) => {
    if (!r) return null;
    let s = 0, any = false;
    r.forEach((v, k) => { if (v !== null) { s += state.dataMode === "q" ? v / qAge(k + 2) : v; any = true; } });
    return any ? s : null;
  });

  function renderTiles() {
    const R = state.res, m = R.meta, Y = R.years.length;
    const tot = state.ages === "all" ? R.total_all_q : R.total_obs_q;
    const last = Y - 1;
    const beta = R.beta1d_q[2];
    const tiles = [
      UI.tile(`Численность, ${R.years[last]}`, pieces(tot[2][last]), `95 %: ${pieces(tot[0][last])} – ${pieces(tot[4][last])}`),
      UI.tile(`Численность, ${R.years[0]}`, pieces(tot[2][0]), `95 %: ${pieces(tot[0][0])} – ${pieces(tot[4][0])}`),
      UI.tile(`Пополнение 0–1, ${R.years[last]}`, pieces(R.X_q[2][last][0]), "медиана"),
      UI.tile("β в среднем", fixed2(beta.reduce((a, b) => a + b, 0) / beta.length), `по годам ${fixed2(Math.min(...beta))} – ${fixed2(Math.max(...beta))}`),
    ];
    if (state.source !== "prior") {
      tiles.push(UI.tile("Расходимостей", f0(m.divergences), `R̂ max: ${m.rhat_X_max ? f3(m.rhat_X_max) : "—"}`));
      tiles.push(UI.tile("Время расчёта", hms(m.seconds), `${m.chains} цепи × ${m.draws_per_chain} выборок`));
    } else {
      tiles.push(UI.tile("Априорных выборок", f0(m.chains * m.draws_per_chain), "без данных, без PyMC"));
    }
    $("tiles").replaceChildren(...tiles);

    const notes = [];
    if (state.source === "prior") notes.push("это априорная проверка: полосы показывают, что допускают априорные распределения до учёта данных; оценки по уловам должны попадать в полосы");
    if (R.config_changed && R.config_changed.length) notes.push(`настройки изменены после этого расчёта (${R.config_changed.join(", ")}) — результаты соответствуют прежним настройкам`);
    if (m.divergences) notes.push(`${m.divergences} расходимостей NUTS: результаты в этих областях ненадёжны; помогают больший target_accept или более узкие априорные распределения`);
    if (m.rhat_X_max && m.rhat_X_max > 1.01) notes.push(`R̂ численности до ${f3(m.rhat_X_max)} (> 1,01): цепи не сошлись, нужно больше выборок или шагов настройки`);
    if (m.numpy_check !== null && m.numpy_check !== undefined && m.numpy_check > 1e-6) notes.push(`численность из PyMC и пересчёт на numpy отличаются на ${num(m.numpy_check * 100)} % — сообщите разработчику`);
    for (const n of m.notes || []) notes.push(n);
    UI.note($("status-note"), notes);
  }

  function renderTotal() {
    const R = state.res, log = state.scale === "log";
    const tot = state.ages === "all" ? R.total_all_q : R.total_obs_q;
    const d = R.data;
    const lines = [{ name: "Модель, медиана", values: tot[2], colorVar: "--series-1", width: 2.5 }];
    const finalT = dataTotal(d.final_by_age);
    if (finalT.some((v) => v !== null)) lines.push({ name: state.dataMode === "q" ? "Окончательный запас по уловам / q" : "Окончательный запас по уловам",
      values: finalT, colorVar: "--series-2", noLine: true, dx: -0.12 });
    else {
      const n = dataTotal(d.net_by_age), s = dataTotal(d.seine_by_age);
      if (n.some((v) => v !== null)) lines.push({ name: "Оценка по сетям (старые данные)", values: n, colorVar: "--series-2", noLine: true, dx: -0.12 });
      if (s.some((v) => v !== null)) lines.push({ name: "Оценка по неводу (старые данные)", values: s, colorVar: "--series-2", noLine: true, dx: 0.12, marker: "diamond" });
    }
    if (d.npc_total && d.npc_total.some((v) => v !== null)) lines.push({ name: "Оценка НПЦ", values: d.npc_total, colorVar: "--series-4", noLine: true, marker: "diamond", dx: 0.12 });
    if (R.old && R.old.total_median && state.ages === "obs") lines.push({ name: "Старый байесовский расчёт", values: R.old.total_median, colorVar: "--series-3", dash: true });
    $("total-title").textContent = `Численность по годам — ${state.species}`;
    $("total-sub").textContent = (state.ages === "all" ? "Все возрасты, включая сеголетки 0–1." : "Возрасты 1–2 и старше (как в уловах).")
      + " Полосы — 50 % и 95 % интервалы модели.";
    Charts.xy($("chart-total"), {
      x: R.years, xTitle: "Год", yTitle: "штук", yLog: log, format: pieces,
      bands: [
        { name: "95 % интервал", lo: tot[0], hi: tot[4], colorVar: "--series-1", opacity: 0.16 },
        { name: "50 % интервал", lo: tot[1], hi: tot[3], colorVar: "--series-1", opacity: 0.32 },
      ],
      lines,
    });
  }

  function renderAges() {
    const R = state.res, i = yi(), log = state.scale === "log";
    const ages = R.model_ages;
    const X = R.X_q.map((q) => q[i]);
    const fin = R.data.final_by_age[i] ? [null, ...R.data.final_by_age[i]] : null;
    const finV = fin ? fin.map((v, k) => (v === null ? null : state.dataMode === "q" && k > 0 ? v / qAge(ages[k]) : v)) : null;
    const lines = [];
    if (finV && finV.some((v) => v !== null)) lines.push({ name: state.dataMode === "q" ? "Оценки по уловам / q" : "Оценки по уловам", values: finV, colorVar: "--series-2", noLine: true, dx: 0.14 });
    if (R.old && R.old.X_median && R.old.X_median[i]) lines.push({ name: "Старый расчёт", values: ages.map((a) => { const k = R.old.ages.indexOf(a); return k >= 0 ? R.old.X_median[i][k] : null; }), colorVar: "--series-3", dash: true });
    $("ages-title").textContent = `Возрастная структура, ${state.year}`;
    Charts.xy($("chart-ages"), {
      x: ages, xLabel: ageLabel, xTitle: AGE_AXIS, yTitle: "штук", yLog: log, format: pieces, tipHead: ageTip,
      intervals: [{ name: "Модель (95 %)", lo: X[0], hi: X[4], mid: X[2], colorVar: "--series-1", dx: -0.1 }],
      lines,
    });
  }

  function renderRecruits() {
    const R = state.res, log = state.scale === "log";
    const q = R.X_q.map((m) => col(m, 0));
    Charts.xy($("chart-recruits"), {
      x: R.years, xTitle: "Год", yTitle: "штук", yLog: log, format: pieces,
      bands: [{ name: "95 %", lo: q[0], hi: q[4], colorVar: "--series-1", opacity: 0.16 },
        { name: "50 %", lo: q[1], hi: q[3], colorVar: "--series-1", opacity: 0.32 }],
      lines: [{ name: "Медиана", values: q[2], colorVar: "--series-1", markers: true }],
    });
  }

  function renderCurves() {
    const R = state.res, i = yi(), ages = R.model_ages;
    const s = R.s_q.map((q) => q[i]), g = R.pred_q.map((q) => q[i]);
    const oldLine = (key) => (R.old && R.old[key] && R.old[key][i]
      ? [{ name: "Старый расчёт", values: ages.map((a) => { const k = R.old.ages.indexOf(a); return k >= 0 ? R.old[key][i][k] : null; }), colorVar: "--series-3", dash: true }] : []);
    $("s-title").textContent = `Естественная смертность s по возрастам, ${state.year}`;
    $("pred-title").textContent = `Давление хищников γ по возрастам, ${state.year}`;
    const share = (v) => (v === null || v === undefined ? "—" : Charts.nf(3).format(v));
    Charts.xy($("chart-s"), {
      x: ages, xLabel: ageLabel, xTitle: AGE_AXIS, yTitle: "доля за год", format: share, tipHead: ageTip,
      bands: [{ name: "95 %", lo: s[0], hi: s[4], colorVar: "--series-1", opacity: 0.2 }],
      lines: [{ name: "Медиана", values: s[2], colorVar: "--series-1", markers: true }, ...oldLine("s_median")],
      vrefs: [{ x: R.meta.m0 + 1, label: "m0 + 1", dash: true }],
    });
    Charts.xy($("chart-pred"), {
      x: ages, xLabel: ageLabel, xTitle: AGE_AXIS, yTitle: "γ", format: share, tipHead: ageTip,
      bands: [{ name: "95 %", lo: g[0], hi: g[4], colorVar: "--series-1", opacity: 0.2 }],
      lines: [{ name: "Медиана", values: g[2], colorVar: "--series-1", markers: true }, ...oldLine("pred_press_median")],
      vrefs: R.meta.m2 < ages[ages.length - 1] ? [{ x: R.meta.m2 + 0.5, label: "m2", dash: true }] : [],
    });
  }

  function renderBetaQ() {
    const R = state.res, b = R.beta1d_q;
    const lines = [{ name: "Медиана", values: b[2], colorVar: "--series-1", markers: true }];
    if (R.old && R.old.beta) lines.push({ name: "Старый расчёт", values: R.old.beta, colorVar: "--series-3", dash: true });
    Charts.xy($("chart-beta"), {
      x: R.years, xTitle: "Год", yTitle: "β", format: f2,
      bands: [{ name: "95 %", lo: b[0], hi: b[4], colorVar: "--series-1", opacity: 0.16 },
        { name: "50 %", lo: b[1], hi: b[3], colorVar: "--series-1", opacity: 0.32 }],
      lines, refs: [{ y: 1, label: "β = 1" }],
    });
    const ages = R.model_ages, q = R.q_bias_q;
    const from = R.config_used.likelihood_from || 3;
    const ql = [];
    if (R.old && R.old.q_bias) ql.push({ name: "Старый расчёт", values: ages.map((a) => { const k = R.old.ages.indexOf(a); return k >= 0 ? R.old.q_bias[k] : null; }), colorVar: "--series-3", dash: true });
    $("q-sub").textContent = `Оценка по лову ≈ q · численность модели. В правдоподобии — возрасты с ${ageLabel(from)}; для младших q не оценивается по данным.`;
    Charts.xy($("chart-q"), {
      x: ages, xLabel: ageLabel, xTitle: AGE_AXIS, yTitle: "q", yLog: true, format: f2, tipHead: ageTip,
      intervals: [{ name: "q (95 %)", lo: q[0], hi: q[4], mid: q[2], colorVar: "--series-1" }],
      lines: ql, refs: [{ y: 1, label: "q = 1" }],
      vrefs: [{ x: from - 0.5, label: "в правдоподобии →", dash: true }],
    });
  }

  function renderDeaths() {
    const R = state.res, d = R.deaths;
    Charts.xy($("chart-deaths"), {
      x: R.years, xTitle: "Год", yTitle: "штук", yLog: state.scale === "log", format: pieces,
      barGroups: [
        { name: "Естественная гибель", values: d.natural, colorVar: "--series-1" },
        { name: "Хищники", values: d.predators, colorVar: "--series-2" },
        { name: "ПДУ", values: d.catch, colorVar: "--series-3" },
        { name: "Браконьерство", values: d.poaching.map((v) => (v > 0 ? v : null)), colorVar: "--series-4" },
      ],
    });
  }

  function renderParams() {
    const R = state.res, t = $("params-table"); t.replaceChildren();
    UI.head(t, ["Параметр", "Год / возраст", "Медиана", "95 % интервал", "50 % интервал", "R̂"], ["Параметр"]);
    const tb = document.createElement("tbody");
    const rh = (v) => (v === null || v === undefined ? "—" : f3(v));
    const bad = (v) => (v && v > 1.01 ? "rhat-bad" : "");
    const addRow = (r, cls) => {
      const tr = document.createElement("tr"); if (cls) tr.className = cls;
      UI.cell(tr, r.label);
      UI.cell(tr, r.index === null ? "—" : r.name === "q_bias" ? ageTitle(r.index) : r.index);
      UI.cell(tr, num(r.q[2])); UI.cell(tr, `${num(r.q[0])} – ${num(r.q[4])}`); UI.cell(tr, `${num(r.q[1])} – ${num(r.q[3])}`);
      UI.cell(tr, rh(r.rhat), bad(r.rhat));
      tb.appendChild(tr);
    };
    const groups = new Map();
    for (const r of R.param_rows) {
      if (r.index === null) { addRow(r); continue; }
      if (!groups.has(r.name)) groups.set(r.name, []);
      groups.get(r.name).push(r);
    }
    for (const [name, rows] of groups) {
      const open = state.expanded.has(name);
      const med = rows.map((r) => r.q[2]), lo = rows.map((r) => r.q[0]), hi = rows.map((r) => r.q[4]);
      const rhMax = Math.max(...rows.map((r) => r.rhat || 0)) || null;
      const tr = document.createElement("tr"); tr.className = "clickable group-row";
      tr.title = open ? "Свернуть" : "Показать по годам / возрастам";
      UI.cell(tr, `${open ? "▾" : "▸"} ${rows[0].label}`);
      UI.cell(tr, name === "q_bias" ? `${rows.length} возрастов` : `${rows.length} лет`);
      UI.cell(tr, `${num(Math.min(...med))} – ${num(Math.max(...med))}`);
      UI.cell(tr, `${num(Math.min(...lo))} – ${num(Math.max(...hi))}`);
      UI.cell(tr, "");
      UI.cell(tr, rh(rhMax), bad(rhMax));
      tr.addEventListener("click", () => { if (open) state.expanded.delete(name); else state.expanded.add(name); renderParams(); });
      tb.appendChild(tr);
      if (open) rows.forEach((r) => addRow({ ...r, label: "" }, "sub-row"));
    }
    t.appendChild(tb);
  }

  function renderDiag() {
    const R = state.res, m = R.meta, t = $("diag-table"); t.replaceChildren();
    UI.head(t, ["Показатель", "Значение"], ["Показатель", "Значение"]);
    const rows = [
      ["Режим", m.mode_title], ["Начало", dt(m.started)], ["Окончание", dt(m.finished)], ["Время", hms(m.seconds)],
      ["Цепей × выборок", `${m.chains} × ${m.draws_per_chain}`], ["Шагов настройки (tune)", m.tune],
      ["Расходимостей", m.divergences === null ? "—" : `${m.divergences}` + (m.divergences_by_chain ? ` (по цепям: ${m.divergences_by_chain.join(", ")})` : "")],
      ["Достигнута max_treedepth", m.treedepth_hits ?? "—"], ["Средний шаг", m.step_size ? num(m.step_size) : "—"],
      ["Средняя доля принятия", m.acceptance_rate ? f3(m.acceptance_rate) : "—"],
      ["R̂ численности, max", m.rhat_X_max ? f3(m.rhat_X_max) : "—"],
      ["Сверка уравнений PyMC и numpy", m.numpy_check === null || m.numpy_check === undefined ? "—" : `отличие ${m.numpy_check.toExponential(1)}`],
      ["Ловов в правдоподобии", m.n_obs + (m.dropped ? ` (исключено ${m.dropped})` : "")],
      ["m0 / m1 / m2", `${m.m0} / ${m.m1} / ${m.m2}`],
    ];
    if (R.old && !R.old.error) rows.push(["Старый расчёт", `${R.old.file}: расходимостей ${R.old.divergences ?? "—"}, R̂ max ${R.old.rhat_X_max ? f3(R.old.rhat_X_max) : "—"}`]);
    if (R.old && R.old.error) rows.push(["Старый расчёт", `не прочитан: ${R.old.error}`]);
    const tb = document.createElement("tbody");
    for (const [k, v] of rows) { const tr = document.createElement("tr"); UI.cell(tr, k); UI.cell(tr, String(v ?? "—"), "text"); tb.appendChild(tr); }
    t.appendChild(tb);

    // как в старом файле: сумма медиан по возрастам 1–2 и старше
    const sumMed = R.X_q[2].map((r) => r.slice(1).reduce((a, v) => a + (v || 0), 0));
    const cmp = m.check_vs_old || (R.old && R.old.total_median ? {
      rows: R.years.map((y, k) => ({ year: y, old: R.old.total_median[k], new: sumMed[k],
        rel: R.old.total_median[k] ? (sumMed[k] - R.old.total_median[k]) / R.old.total_median[k] : null })) } : null);
    $("check-block").hidden = !cmp;
    if (cmp) {
      const ct = $("check-table"); ct.replaceChildren();
      UI.head(ct, ["Год", "Старый расчёт", "Этот расчёт", "Отличие"]);
      const b2 = document.createElement("tbody");
      for (const r of cmp.rows) {
        const tr = document.createElement("tr");
        UI.cell(tr, r.year); UI.cell(tr, pieces(r.old)); UI.cell(tr, pieces(r.new));
        UI.cell(tr, r.rel === null ? "—" : `${r.rel > 0 ? "+" : ""}${Charts.nf(1).format(r.rel * 100)} %`);
        b2.appendChild(tr);
      }
      ct.appendChild(b2);
    }
  }

  init();
})();
