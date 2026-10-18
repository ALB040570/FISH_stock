/* Страница «Уловистость невода» */
(() => {
  const API = "/api/catchability/seine";
  const state = { data: null, species: null, year: null, scale: "linear" };
  const $ = (id) => document.getElementById(id);
  const f2 = (v) => (v === null || v === undefined ? "—" : Charts.nf(2).format(v));
  const f1 = (v) => (v === null || v === undefined ? "—" : Charts.nf(1).format(v));
  const f3 = (v) => (v === null || v === undefined ? "—" : Charts.nf(3).format(v));
  const f0 = (v) => (v === null || v === undefined ? "—" : Charts.nf(0).format(v));

  async function load(method = "GET", url = API) {
    const content = $("content");
    content.style.opacity = state.data ? 0.5 : 1;
    try {
      const resp = await fetch(url, { method });
      if (!resp.ok) throw new Error(`${resp.status} ${await resp.text()}`);
      state.data = await resp.json();
      if (!state.species || !state.data.species.includes(state.species)) state.species = UI.initialSpecies(state.data.species);
      if (!state.year || !state.data.years.includes(state.year)) state.year = state.data.years[state.data.years.length - 1];
      $("load-state").hidden = true;
      content.hidden = false;
      buildFilters();
      render();
    } catch (e) {
      $("load-state").hidden = false;
      $("load-state").textContent = `Ошибка загрузки: ${e.message}`;
    } finally {
      content.style.opacity = 1;
    }
  }

  // ---------- фильтры ----------
  function buildFilters() {
    const tabs = $("species-tabs");
    tabs.replaceChildren();
    for (const s of state.data.species) {
      const b = document.createElement("button");
      b.textContent = s[0].toUpperCase() + s.slice(1);
      b.className = s === state.species ? "on" : "";
      b.setAttribute("role", "tab");
      b.addEventListener("click", () => { state.species = s; buildFilters(); render(); });
      tabs.appendChild(b);
    }
    const sel = $("year-select");
    sel.replaceChildren();
    for (const y of state.data.years) {
      const o = document.createElement("option"); o.value = y; o.textContent = y;
      if (y === state.year) o.selected = true;
      sel.appendChild(o);
    }
  }
  $("year-select").addEventListener("change", (e) => { state.year = +e.target.value; render(); });
  document.querySelectorAll("#scale-toggle button").forEach((b) =>
    b.addEventListener("click", () => {
      state.scale = b.dataset.scale;
      document.querySelectorAll("#scale-toggle button").forEach((x) => x.classList.toggle("on", x === b));
      renderCatchChart(current());
    }));
  function selectYear(y) { state.year = y; $("year-select").value = y; render(); }

  const current = () => state.data.fits[state.species][String(state.year)];

  // ---------- отрисовка ----------
  function render() {
    const d = current();
    renderTiles(d);
    renderCatchChart(d);
    renderCChart(d);
    renderAgeTable(d);
    renderHeat();
    renderParams();
    const info = [`Расчёт: ${state.data.computed_at}`, `исходные данные: ${state.data.source_dir}`];
    if (state.data.saved.nc) info.push(`сохранено: ${state.data.saved.nc}`);
    else if (state.data.saved.csv) info.push(`сохранено: ${state.data.saved.csv}`);
    if (state.data.saved.nc_error) info.push(`.nc не записан: ${state.data.saved.nc_error}`);
    if (state.data.saved.error) info.push(`ошибка записи: ${state.data.saved.error}`);
    if (state.data.old_error) info.push(`прежние коэффициенты не прочитаны: ${state.data.old_error}`);
    $("footer-info").textContent = info.join(" · ");
  }

  function tile(label, value, sub) {
    const t = document.createElement("div"); t.className = "tile";
    const l = document.createElement("div"); l.className = "tile-label"; l.textContent = label;
    const v = document.createElement("div"); v.className = "tile-value"; v.textContent = value;
    t.append(l, v);
    if (sub) { const s = document.createElement("div"); s.className = "tile-sub"; s.textContent = sub; t.appendChild(s); }
    return t;
  }

  function renderTiles(d) {
    const c = d.c;
    $("tiles").replaceChildren(
      tile("Точка перегиба j50", f1(d.j50), `номер возраста; по правилу статьи: ${f0(d.j50_rule)} (возраст ${UI.ageLabel(d.j50_rule)})`),
      tile("Крутизна a", f2(d.a), "1/год"),
      tile("Уловистость по возрастам", `${f2(c[0])} … ${f2(c[c.length - 1])}`, `средняя ${f2(d.c_mean)} (задана)`),
      tile("Общая смертность Z", f2(d.Z), "из кривой улова, 1/год"),
      tile("Качество подгонки R²", f2(d.r2), "в логарифмах, взвешенно"),
      tile("Данные года", `${f0(d.n_sample)} рыб`, `в пробе; неводом ${f0(d.total_catch)} шт за ${d.n_hauls} уловов`),
    );
    const note = $("status-note");
    if (d.status && d.status !== "ок") {
      note.replaceChildren();
      const icon = document.createElement("span"); icon.className = "icon"; icon.textContent = "⚠";
      const text = document.createElement("span");
      const parts = [];
      if (d.first_lower_active) parts.push(`уловистость двухлеток (возраст 1–2) упёрлась в нижнюю границу ${f2(state.data.c_lower_first)}`);
      if (d.lower_active) parts.push(`уловистость возраста 2–3 упёрлась в нижнюю границу ${f1(state.data.c_lower)}`);
      if (d.first_lower_active || d.lower_active) parts.push("без ограничения МНК дал бы меньшее значение");
      if (d.upper_active) parts.push(`уловистость в ${d.m1} лет упёрлась в верхнюю границу ${f1(state.data.c_upper)}`);
      if (!d.observed_is_catch) parts.push(`данные: ${d.source}`);
      if (d.status.includes("ступенька")) parts.push("сигмоида почти ступенька (a на верхней границе)");
      text.textContent = "Обратите внимание: " + parts.join("; ") + ".";
      note.append(icon, text);
      note.hidden = false;
    } else note.hidden = true;
  }

  function renderCatchChart(d) {
    const isCatch = d.observed_is_catch;
    const obsName = isCatch ? "Факт: улов, шт" : "Факт: доля в пробе";
    const log = state.scale === "log";
    $("catch-title").textContent = isCatch ? "Улов неводом по возрастам" : "Возрастная проба (вместо улова)";
    $("catch-sub").textContent = `${cap(state.species)}, ${state.year}. Модель: c·N0·exp(−Z·j)` +
      (log ? " — в логарифмической шкале кривая улова почти прямая справа от перегиба" : "");
    const spec = {
      x: d.ages, xLabel: UI.ageLabel, xTitle: UI.AGE_AXIS, yTitle: isCatch ? "штук" : "доля",
      yLog: log,
      lines: [{ name: "МНК-модель", values: d.fitted, colorVar: "--series-1", markers: false }],
      format: isCatch ? f0auto : f3,
      tipHead: UI.ageTip,
    };
    if (log) spec.points = { name: obsName, values: d.observed, colorVar: "--observed-hover" };
    else spec.bars = { name: obsName, values: d.observed, colorVar: "--observed", hoverVar: "--observed-hover" };
    Charts.xy($("chart-catch"), spec);
  }
  const f0auto = (v) => (v === null || v === undefined ? "—" : Math.abs(v) >= 10 ? f0(v) : f2(v));

  function renderCChart(d) {
    const hasOld = Array.isArray(d.c_old) && d.c_old.some((v) => v !== null);
    $("c-sub").textContent = hasOld
      ? "Сплошная — МНК (новый расчёт), пунктир — прежний байесовский расчёт"
      : state.data.old_available ? "Прежних коэффициентов для этого вида и года нет"
        : "Прежние коэффициенты не загружены (нужны xarray и netCDF4 и файл в data_stock)";
    const vrefs = [{ x: d.j50, label: `j50 = ${f1(d.j50)}` }];
    if (Math.abs(d.j50_rule - d.j50) > 0.05) vrefs.push({ x: d.j50_rule, label: `по статье: ${UI.ageLabel(d.j50_rule)}`, dash: true, row: 1 });
    Charts.xy($("chart-c"), {
      x: d.ages, xLabel: UI.ageLabel, xTitle: UI.AGE_AXIS, yTitle: "коэффициент",
      yDomain: [0, 0.9],
      lines: [
        { name: "МНК (новый)", values: d.c, colorVar: "--series-1", markers: true },
        { name: "Байес (прежний)", values: hasOld ? d.c_old : null, colorVar: "--series-2", dash: true },
      ],
      refs: [{ y: state.data.c_lower, label: "мин 0,1 (с возраста 2–3)" }, { y: state.data.c_upper, label: "макс 0,8" }],
      vrefs, format: f2, tipHead: UI.ageTip,
    });
  }

  function cell(tr, text, cls) { const td = document.createElement("td"); td.textContent = text; if (cls) td.className = cls; tr.appendChild(td); }
  function head(table, cols, textCols = []) {
    const thead = document.createElement("thead"); const tr = document.createElement("tr");
    for (const c of cols) { const th = document.createElement("th"); th.textContent = c;
      if (textCols.includes(c)) th.className = "text"; tr.appendChild(th); }
    thead.appendChild(tr); table.appendChild(thead);
  }

  function renderAgeTable(d) {
    const t = $("age-table"); t.replaceChildren();
    head(t, ["Возраст", d.observed_is_catch ? "Улов факт, шт" : "Доля в пробе", "Улов модель", "Вес МНК", "c МНК", "c байес (прежний)"]);
    const tb = document.createElement("tbody");
    d.ages.forEach((a, i) => {
      const tr = document.createElement("tr");
      cell(tr, UI.ageTitle(a)); cell(tr, f0auto(d.observed[i])); cell(tr, f0auto(d.fitted[i])); cell(tr, f0(d.weights[i]));
      cell(tr, f3(d.c[i])); cell(tr, d.c_old ? f3(d.c_old[i]) : "—");
      tb.appendChild(tr);
    });
    t.appendChild(tb);
  }

  function renderHeat() {
    const bySpecies = state.data.fits[state.species];
    const years = state.data.years;
    const ages = bySpecies[String(years[0])].ages;
    $("heat-title").textContent = `Уловистость невода по годам и возрастам — ${state.species}`;
    Charts.heatmap($("chart-heat"), {
      cols: ages, rows: years,
      z: years.map((y) => ages.map((a, i) => bySpecies[String(y)].c[i])),
      domain: [0, state.data.c_upper],
      selectedRow: state.year, onRowClick: selectYear,
      colLabel: (a) => `возраст ${UI.ageTitle(a)}`, colTick: UI.ageLabel, colTitle: UI.AGE_AXIS, valueName: "c",
      format: f2,
    });
  }

  function renderParams() {
    $("params-title").textContent = `Параметры сигмоид по годам — ${state.species}`;
    const t = $("params-table"); t.replaceChildren();
    head(t, ["Год", "a", "j50 МНК", "j50 статья", "Z", "b", "c(2)", "c(m1)", "R²", "Рыб в пробе", "Улов неводом, шт", "Примечание"], ["Примечание"]);
    const tb = document.createElement("tbody");
    for (const y of state.data.years) {
      const d = state.data.fits[state.species][String(y)];
      const tr = document.createElement("tr");
      tr.className = "clickable" + (y === state.year ? " selected" : "");
      tr.addEventListener("click", () => selectYear(y));
      cell(tr, y); cell(tr, f2(d.a)); cell(tr, f2(d.j50)); cell(tr, f0(d.j50_rule)); cell(tr, f2(d.Z));
      cell(tr, f3(d.b)); cell(tr, f3(d.c[0])); cell(tr, f3(d.c[d.c.length - 1])); cell(tr, f2(d.r2));
      cell(tr, f0(d.n_sample)); cell(tr, f0(d.total_catch)); cell(tr, d.status, "text");
      tb.appendChild(tr);
    }
    t.appendChild(tb);
  }

  const cap = (s) => s[0].toUpperCase() + s.slice(1);

  $("btn-recalc").addEventListener("click", async (e) => {
    const b = e.currentTarget; b.disabled = true; b.textContent = "Считаю…";
    await load("POST", `${API}/recalculate`);
    b.disabled = false; b.textContent = "Пересчитать";
  });

  load();
})();
