/* Страница «Уловистость сети» */
(() => {
  const API = "/api/catchability/net";
  const { f0, f1, f2, f3, cap, ageLabel, ageTitle, ageTip, AGE_AXIS } = UI;
  const state = { data: null, species: null, year: null };
  const $ = (id) => document.getElementById(id);

  async function load() {
    try {
      state.data = await UI.fetchJSON(API);
      state.species = state.species || UI.initialSpecies(state.data.species);
      state.year = state.year || state.data.years[state.data.years.length - 1];
      $("load-state").hidden = true; $("content").hidden = false;
      buildFilters(); render();
    } catch (e) {
      $("load-state").textContent = `Ошибка загрузки: ${e.message}`;
    }
  }

  function buildFilters() {
    UI.segmented($("species-tabs"), state.data.species.map((s) => ({ value: s, label: cap(s) })), state.species,
      (s) => { state.species = s; buildFilters(); render(); });
    UI.yearSelect($("year-select"), state.data.years, state.year);
  }
  $("year-select").addEventListener("change", (e) => { state.year = +e.target.value; render(); });
  const selectYear = (y) => { state.year = y; $("year-select").value = y; render(); };
  const current = () => state.data.fits[state.species][String(state.year)];

  function render() {
    const d = current();
    const c = d.c;
    const iPeak = d.ages.indexOf(d.peak);
    $("tiles").replaceChildren(
      UI.tile("Вершина параболы c¹", `возраст ${ageLabel(d.peak)}`, `номер возраста j = ${f0(d.peak)}`),
      UI.tile("Уловистость в вершине c⁰", f3(d.c0), `средняя ${f2(d.c_mean)} (задана)`),
      UI.tile("Уловистость по возрастам", `${f2(Math.min(...c))} – ${f2(Math.max(...c))}`,
        `c(${ageLabel(d.ages[0])}) = ${f2(c[0])}, c(${ageLabel(d.m1)}) = ${f2(c[c.length - 1])}`),
      UI.tile("Ветви a1 / a2", `${f3(d.a1)} / ${f3(d.a2)}`, "левая / правая"),
      UI.tile("Доля в сети σ (вершина)", iPeak >= 0 ? f3(d.sigma[iPeak]) : "—",
        `${f0(d.hours)} ч, сеть ${f0(d.net_length)} м, ${f0(d.speed)} м/ч`),
      UI.tile("Данные года", `${f0(d.n_sample)} рыб`, `в пробе; сетью ${f0(d.total_catch)} шт за ${d.n_hauls} уловов`),
    );
    const parts = [];
    if (d.status && d.status !== "ок") parts.push(d.status);
    UI.note($("status-note"), parts);

    const isCatch = d.observed_is_catch;
    $("catch-title").textContent = isCatch ? "Улов сетью по возрастам" : "Возрастная проба (вместо улова)";
    $("catch-sub").textContent = `${cap(state.species)}, ${state.year}. Вертикальная линия — вершина параболы c¹.`;
    Charts.xy($("chart-catch"), {
      x: d.ages, xLabel: ageLabel, xTitle: AGE_AXIS, yTitle: isCatch ? "штук" : "доля",
      bars: { name: isCatch ? "Улов, шт" : "Доля в пробе", values: d.observed, colorVar: "--observed", hoverVar: "--observed-hover" },
      vrefs: [{ x: d.peak, label: `вершина ${ageLabel(d.peak)}` }],
      format: isCatch ? (v) => (v === null ? "—" : Math.abs(v) >= 10 ? f0(v) : f2(v)) : f3,
      tipHead: ageTip,
    });

    const hasOld = Array.isArray(d.c_old) && d.c_old.some((v) => v !== null);
    $("c-sub").textContent = hasOld ? "Сплошная — парабола (статья), пунктир — прежний расчёт (логистический «колокол»)"
      : "Прежние коэффициенты не загружены (нужны xarray и netCDF4 и файл в data_stock)";
    Charts.xy($("chart-c"), {
      x: d.ages, xLabel: ageLabel, xTitle: AGE_AXIS, yTitle: "коэффициент", yDomain: [0, 0.9],
      lines: [
        { name: "Парабола (22)–(24)", values: c, colorVar: "--series-1", markers: true },
        { name: "Прежний расчёт", values: hasOld ? d.c_old : null, colorVar: "--series-2", dash: true },
      ],
      refs: [{ y: d.c_lower, label: `мин c̄/3 = ${f2(d.c_lower)}` }, { y: state.data.c_upper, label: "макс 0,8" }],
      vrefs: [{ x: d.peak, label: `вершина ${ageLabel(d.peak)}` }],
      format: f2, tipHead: ageTip,
    });

    // таблица по возрастам
    const t = $("age-table"); t.replaceChildren();
    UI.head(t, ["Возраст", isCatch ? "Улов, шт" : "Доля в пробе", "c парабола", "c прежний", "σ (доля в сети)"]);
    const tb = document.createElement("tbody");
    d.ages.forEach((a, i) => {
      const tr = document.createElement("tr");
      UI.cell(tr, ageTitle(a)); UI.cell(tr, isCatch ? f0(d.observed[i]) : f3(d.observed[i]));
      UI.cell(tr, f3(c[i])); UI.cell(tr, hasOld ? f3(d.c_old[i]) : "—"); UI.cell(tr, f3(d.sigma[i]));
      tb.appendChild(tr);
    });
    t.appendChild(tb);

    renderHeat(); renderParams();
    UI.footer($("footer-info"), state.data);
  }

  function renderHeat() {
    const by = state.data.fits[state.species], years = state.data.years;
    const ages = by[String(years[0])].ages;
    $("heat-title").textContent = `Уловистость сети по годам и возрастам — ${state.species}`;
    Charts.heatmap($("chart-heat"), {
      cols: ages, rows: years, z: years.map((y) => by[String(y)].c),
      domain: [0, state.data.c_upper], selectedRow: state.year, onRowClick: selectYear,
      colLabel: (a) => `возраст ${ageTitle(a)}`, colTick: ageLabel, colTitle: AGE_AXIS, valueName: "c", format: f2,
    });
  }

  function renderParams() {
    $("params-title").textContent = `Параметры парабол по годам — ${state.species}`;
    const t = $("params-table"); t.replaceChildren();
    UI.head(t, ["Год", "Вершина (возраст)", "c⁰", "a1", "a2", "c первого возраста", "c(m1)", "Рыб в пробе", "Улов сетью, шт", "Уловов", "Примечание"], ["Примечание"]);
    const tb = document.createElement("tbody");
    for (const y of state.data.years) {
      const d = state.data.fits[state.species][String(y)];
      const tr = document.createElement("tr");
      tr.className = "clickable" + (y === state.year ? " selected" : "");
      tr.addEventListener("click", () => selectYear(y));
      UI.cell(tr, y); UI.cell(tr, ageLabel(d.peak)); UI.cell(tr, f3(d.c0)); UI.cell(tr, f3(d.a1)); UI.cell(tr, f3(d.a2));
      UI.cell(tr, f3(d.c[0])); UI.cell(tr, f3(d.c[d.c.length - 1])); UI.cell(tr, f0(d.n_sample));
      UI.cell(tr, f0(d.total_catch)); UI.cell(tr, d.n_hauls); UI.cell(tr, d.status, "text");
      tb.appendChild(tr);
    }
    t.appendChild(tb);
  }

  load();
})();
