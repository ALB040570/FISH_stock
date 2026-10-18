/* Страница «Запас по уловам» */
(() => {
  const API = "/api/stock";
  const { f0, f1, f2, cap, ageLabel, ageTip, AGE_AXIS } = UI;
  const state = { data: null, species: null, variant: "with_ages", method: "on_stock", scale: "log",
    year: null, showOld: false };
  const $ = (id) => document.getElementById(id);

  // штуки -> компактно: 1,2 млн / 350 тыс / 820
  function pieces(v) {
    if (v === null || v === undefined || !Number.isFinite(v)) return "—";
    const a = Math.abs(v);
    if (a >= 1e9) return `${Charts.nf(a >= 1e10 ? 0 : 1).format(v / 1e9)} млрд`;
    if (a >= 1e6) return `${Charts.nf(a >= 1e8 ? 0 : a >= 1e7 ? 1 : 2).format(v / 1e6)} млн`;
    if (a >= 1e3) return `${Charts.nf(a >= 1e5 ? 0 : 1).format(v / 1e3)} тыс`;
    return f0(v);
  }

  async function load(method = "GET", url = API) {
    const content = $("content");
    content.style.opacity = state.data ? 0.5 : 1;
    try {
      state.data = await UI.fetchJSON(url, method);
      const d = state.data;
      if (!state.species || !d.species_list.includes(state.species)) state.species = UI.initialSpecies(d.species_list);
      if (!state.year || !d.years.includes(state.year)) state.year = d.years[d.years.length - 1];
      $("load-state").hidden = true; content.hidden = false;
      $("old-field").hidden = !d.old_available;
      buildFilters(); render();
    } catch (e) {
      $("load-state").hidden = false;
      $("load-state").textContent = `Ошибка загрузки: ${e.message}`;
    } finally {
      content.style.opacity = 1;
    }
  }

  function buildFilters() {
    const d = state.data;
    UI.segmented($("species-tabs"), d.species_list.map((s) => ({ value: s, label: cap(s) })), state.species,
      (s) => { state.species = s; buildFilters(); render(); });
    UI.segmented($("variant-toggle"), [{ value: "with_ages", label: "по возрастам" }, { value: "out_ages", label: "средняя по виду" }],
      state.variant, (v) => { state.variant = v; buildFilters(); render(); });
    UI.segmented($("method-toggle"), [{ value: "on_stock", label: "по запасам" }, { value: "on_catch", label: "по улову" }],
      state.method, (v) => { state.method = v; buildFilters(); render(); });
    UI.segmented($("scale-toggle"), [{ value: "log", label: "Логарифм." }, { value: "linear", label: "Линейная" }],
      state.scale, (v) => { state.scale = v; buildFilters(); render(); });
    UI.yearSelect($("year-select"), d.years, state.year);
  }
  $("year-select").addEventListener("change", (e) => { state.year = +e.target.value; render(); });
  $("show-old").addEventListener("change", (e) => { state.showOld = e.target.checked; render(); });
  const selectYear = (y) => { state.year = y; $("year-select").value = y; render(); };

  function render() {
    const d = state.data, G = d.gears;
    const sp = d.species[state.species];
    const vb = sp.variants[state.variant];
    const mb = vb[state.method];
    const years = d.years, yi = years.indexOf(state.year);
    const net = mb.totals[G.net], seine = mb.totals[G.seine], mean = mb.totals[G.mean], npc = sp.npc;
    const combined = mean;
    const combName = "Сети и невод (окончательный)";
    const combHow = d.combine_how === "hauls" ? "средневзвешенное по числу ловов" : "среднее (29)";
    const log = state.scale === "log";

    // --- плитки ---
    const ratio = net[yi] && seine[yi] ? seine[yi] / net[yi] : null;
    $("tiles").replaceChildren(
      UI.tile(`Сети, ${state.year}`, pieces(net[yi]), d.net_formula === "article" ? "балансовый метод, формула (28)" : "балансовый метод (как в старом коде)"),
      UI.tile(`Невод, ${state.year}`, pieces(seine[yi]), "метод площадей (27)"),
      UI.tile("Окончательный запас", pieces(combined[yi]), `сети и невод: ${combHow}`),
      UI.tile("Оценка НПЦ", npc ? pieces(npc[yi]) : "—", "из zhaysan_npc_assessment"),
      UI.tile("Невод / сети", ratio ? `${f1(ratio)}×` : "—", "во сколько раз больше"),
      UI.tile("Ловов за год", `${f0(sp.n_hauls[G.net][yi])} / ${f0(sp.n_hauls[G.seine][yi])}`, "сетью / неводом"),
    );

    // --- годовой запас ---
    $("yearly-title").textContent = `Годовой запас — ${state.species}`;
    $("yearly-sub").textContent = `${d.method_titles[state.method]}; уловистость ${state.variant === "with_ages"
      ? "по возрастам" : "средняя по виду"}. Штук рыб, все возрасты от 1–2 до m1 (без сеголеток).`;
    const lines = [
      { name: "Сети (балансовый)", values: net, colorVar: "--series-1", markers: true },
      { name: "Невод (27)", values: seine, colorVar: "--series-2", markers: true },
      { name: combName, values: combined, colorVar: "--series-3", markers: true },
    ];
    if (npc) lines.push({ name: "НПЦ", values: npc, colorVar: "--series-4", markers: true });
    if (state.showOld && mb.old_totals[G.net]) lines.push({ name: "Сети, прежний расчёт", values: mb.old_totals[G.net], colorVar: "--series-1", dash: true });
    if (state.showOld && mb.old_totals[G.seine]) lines.push({ name: "Невод, прежний расчёт", values: mb.old_totals[G.seine], colorVar: "--series-2", dash: true });
    Charts.xy($("chart-yearly"), {
      x: years, xTitle: "Год", yTitle: "штук", yLog: log, lines, format: pieces,
      vrefs: [{ x: state.year, label: String(state.year), dash: true }],
    });

    // --- оценки по ловам ---
    const hauls = d.hauls;
    const dots = [G.net, G.seine].map((g, k) => ({
      name: g === G.net ? "Сети, лов" : "Невод, лов", colorVar: k === 0 ? "--series-1" : "--series-2",
      points: vb.hauls[g].map((v, h) => ({
        i: years.indexOf(hauls[g].year[h]), y: v,
        label: `${hauls[g].date[h]}, ${hauls[g].place[h]} (${hauls[g].type[h]})`,
      })).filter((p) => p.y !== null && p.i >= 0),
    }));
    Charts.xy($("chart-hauls"), {
      x: years, xTitle: "Год", yTitle: "штук", yLog: log, format: pieces, dots,
      lines: [
        { name: "Сети, год", values: vb.on_stock.totals[G.net], colorVar: "--series-1" },
        { name: "Невод, год", values: vb.on_stock.totals[G.seine], colorVar: "--series-2" },
      ],
    });

    // --- возрастная структура ---
    $("ages-title").textContent = `Возрастная структура запаса, ${state.year}`;
    $("ages-sub").textContent = `${cap(state.species)}; ${d.method_titles[state.method]}.`;
    Charts.xy($("chart-ages"), {
      x: sp.ages, xLabel: ageLabel, xTitle: AGE_AXIS, yTitle: "штук", yLog: log, format: pieces, tipHead: ageTip,
      barGroups: [
        { name: "Сети", values: mb.by_age[G.net][yi], colorVar: "--series-1" },
        { name: "Невод", values: mb.by_age[G.seine][yi], colorVar: "--series-2" },
      ],
      lines: [{ name: "Окончательный (по нему распределяется ПДУ)", values: mb.by_age[G.mean][yi], colorVar: "--series-3", markers: true }],
    });

    renderTable(net, seine, mean, combined, npc, sp, mb);
    UI.footer($("footer-info"), d);
  }

  function renderTable(net, seine, mean, combined, npc, sp, mb) {
    const d = state.data, G = d.gears;
    $("table-title").textContent = `Годовой запас, таблица — ${state.species}`;
    const t = $("yearly-table"); t.replaceChildren();
    const cols = ["Год", "Сети", "Невод", "Окончательный", "НПЦ", "Невод / сети", "Ловов сетью", "Ловов неводом"];
    const hasOld = d.old_available && mb.old_totals[G.net];
    if (hasOld) cols.push("Сети, прежний", "Невод, прежний");
    UI.head(t, cols);
    const tb = document.createElement("tbody");
    d.years.forEach((y, i) => {
      const tr = document.createElement("tr");
      tr.className = "clickable" + (y === state.year ? " selected" : "");
      tr.addEventListener("click", () => selectYear(y));
      UI.cell(tr, y); UI.cell(tr, f0(net[i])); UI.cell(tr, f0(seine[i])); UI.cell(tr, f0(combined[i]));
      UI.cell(tr, npc ? f0(npc[i]) : "—");
      UI.cell(tr, net[i] && seine[i] ? `${f1(seine[i] / net[i])}×` : "—");
      UI.cell(tr, f0(sp.n_hauls[G.net][i])); UI.cell(tr, f0(sp.n_hauls[G.seine][i]));
      if (hasOld) { UI.cell(tr, f0(mb.old_totals[G.net][i])); UI.cell(tr, f0(mb.old_totals[G.seine][i])); }
      tb.appendChild(tr);
    });
    t.appendChild(tb);
  }

  $("btn-recalc").addEventListener("click", async (e) => {
    const b = e.currentTarget; b.disabled = true; b.textContent = "Считаю…";
    await load("POST", `${API}/recalculate`);
    b.disabled = false; b.textContent = "Пересчитать";
  });

  load();
})();
