/* Страница «ПДУ по возрастам» */
(() => {
  const API = "/api/pdu";
  const { f0, f1, f2, cap, ageLabel, ageTitle, ageTip, AGE_AXIS } = UI;
  const state = { data: null, species: null, year: null, scale: "log" };
  const $ = (id) => document.getElementById(id);

  const pieces = (v) => {
    if (v === null || v === undefined || !Number.isFinite(v)) return "—";
    const a = Math.abs(v);
    if (a >= 1e6) return `${Charts.nf(a >= 1e8 ? 0 : a >= 1e7 ? 1 : 2).format(v / 1e6)} млн`;
    if (a >= 1e3) return `${Charts.nf(a >= 1e5 ? 0 : 1).format(v / 1e3)} тыс`;
    return f0(v);
  };
  const tonnes = (v) => (v === null || v === undefined ? "—" : Charts.nf(Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 1 ? 1 : 2).format(v));
  const pct = (v) => (v === null || v === undefined || !Number.isFinite(v) ? "—" : `${Charts.nf(v >= 0.1 ? 0 : 1).format(v * 100)} %`);

  async function load() {
    try {
      state.data = await UI.fetchJSON(API);
      state.species = state.species || UI.initialSpecies(state.data.species_list);
      state.year = state.year || state.data.years[state.data.years.length - 1];
      $("load-state").hidden = true; $("content").hidden = false;
      buildFilters(); render();
    } catch (e) {
      $("load-state").textContent = `Ошибка загрузки: ${e.message}`;
    }
  }

  function buildFilters() {
    const d = state.data;
    UI.segmented($("species-tabs"), d.species_list.map((s) => ({ value: s, label: cap(s) })), state.species,
      (s) => { state.species = s; buildFilters(); render(); });
    UI.yearSelect($("year-select"), d.years, state.year);
    UI.segmented($("scale-toggle"), [{ value: "log", label: "Логарифм." }, { value: "linear", label: "Линейная" }],
      state.scale, (v) => { state.scale = v; buildFilters(); render(); });
  }
  $("year-select").addEventListener("change", (e) => { state.year = +e.target.value; render(); });
  const selectYear = (y) => { state.year = y; $("year-select").value = y; render(); };

  function render() {
    const d = state.data, sp = d.species[state.species];
    const yi = d.years.indexOf(state.year);
    const by = sp.by_year[yi];
    const share = sp.biomass_t[yi] ? sp.pdu_t[yi] / sp.biomass_t[yi] : null;
    const distShare = sp.pdu_t[yi] ? sp.distributed_t[yi] / sp.pdu_t[yi] : null;

    $("tiles").replaceChildren(
      UI.tile(`ПДУ НПЦ, ${state.year}`, `${tonnes(sp.pdu_t[yi])} т`, "официальный"),
      UI.tile("Распределено", `${tonnes(sp.distributed_t[yi])} т`, distShare !== null ? `${pct(distShare)} квоты` : ""),
      UI.tile("Не распределено", `${tonnes(sp.left_t[yi])} т`, sp.stop_reason[yi]),
      UI.tile("ПДУ в штуках", pieces(sp.pieces_total[yi]), `возрасты от ${ageLabel(sp.m0)} (половозрелые)`),
      UI.tile("Доля от промысловой биомассы", pct(share), `биомасса ${tonnes(sp.biomass_t[yi])} т`),
      UI.tile("Итераций", f0(sp.iterations[yi]), "до исчерпания квоты или запаса"),
    );
    const parts = [];
    if (sp.left_t[yi] > 1e-6) parts.push(`не распределено ${tonnes(sp.left_t[yi])} т: ${sp.stop_reason[yi]}`);
    const capped = by.capped.map((c, i) => (c ? ageLabel(sp.ages[i]) : null)).filter(Boolean);
    if (capped.length) parts.push(`ограничение 75 % срабатывало для возрастов ${capped.join(", ")}`);
    const filled = sp.weight_filled.map((f, i) => (f ? sp.ages[i] : null)).filter((v) => v !== null);
    if (filled.length) parts.push(`средний вес возраста ${filled.map(ageLabel).join(", ")} взят от ближайшего младшего возраста`);
    UI.note($("status-note"), parts);

    const log = state.scale === "log";
    $("ages-title").textContent = `Запас и ПДУ по возрастам, ${state.year}`;
    $("ages-sub").textContent = `${cap(state.species)}. Окончательный запас (сети и невод), штук.`;
    Charts.xy($("chart-ages"), {
      x: sp.ages, xLabel: ageLabel, xTitle: AGE_AXIS, yTitle: "штук", yLog: log, format: pieces, tipHead: ageTip,
      barGroups: [
        { name: "Запас", values: by.stock, colorVar: "--series-1" },
        { name: "ПДУ", values: by.pieces.map((v) => (v > 0 ? v : null)), colorVar: "--series-2" },
      ],
      vrefs: [{ x: sp.m0 - 0.5, label: "половозрелые →", dash: true }],
    });
    const maxE = Math.max(0.5, ...by.exploitation.filter((v) => v !== null));
    Charts.xy($("chart-expl"), {
      x: sp.ages, xLabel: ageLabel, xTitle: AGE_AXIS, yTitle: "доля", yDomain: [0, Math.min(1, Math.ceil(maxE * 10) / 10)],
      lines: [{ name: "Доля изъятия", values: by.exploitation.map((v, i) => (sp.ages[i] >= sp.m0 ? v : null)),
        colorVar: "--series-2", markers: true }],
      format: pct, tipHead: ageTip,
    });

    // таблица по возрастам
    const t = $("age-table"); t.replaceChildren();
    UI.head(t, ["Возраст", "Запас, шт", "Средний вес, г", "ПДУ, шт", "ПДУ, т", "Доля изъятия", "Ограничение 75 %"]);
    const tb = document.createElement("tbody");
    sp.ages.forEach((a, i) => {
      const tr = document.createElement("tr");
      UI.cell(tr, ageTitle(a) + (sp.weight_filled[i] ? " *" : ""));
      UI.cell(tr, f0(by.stock[i])); UI.cell(tr, f0(by.weight[i])); UI.cell(tr, f0(by.pieces[i]));
      UI.cell(tr, tonnes(by.tonnes[i])); UI.cell(tr, a >= sp.m0 ? pct(by.exploitation[i]) : "не ловится");
      UI.cell(tr, by.capped[i] ? "да" : "—");
      tb.appendChild(tr);
    });
    t.appendChild(tb);

    // по годам
    $("years-title").textContent = `ПДУ и промысловая биомасса по годам — ${state.species}`;
    const lines = [
      { name: "Промысловая биомасса, т", values: sp.biomass_t, colorVar: "--series-1", markers: true },
      { name: "ПДУ НПЦ, т", values: sp.pdu_t, colorVar: "--series-2", markers: true },
    ];
    if (sp.left_t.some((v) => v > 1e-6)) lines.push({ name: "Распределено, т", values: sp.distributed_t, colorVar: "--series-3", dash: true });
    Charts.xy($("chart-years"), {
      x: d.years, xTitle: "Год", yTitle: "тонн", yLog: log, lines, format: tonnes,
      vrefs: [{ x: state.year, label: String(state.year), dash: true }],
    });

    const tt = $("years-table"); tt.replaceChildren();
    UI.head(tt, ["Год", "ПДУ НПЦ, т", "Распределено, т", "Не распределено, т", "ПДУ, шт", "Промысловая биомасса, т",
      "ПДУ / биомасса", "Итераций", "Остановка"], ["Остановка"]);
    const tb2 = document.createElement("tbody");
    d.years.forEach((y, i) => {
      const tr = document.createElement("tr");
      tr.className = "clickable" + (y === state.year ? " selected" : "");
      tr.addEventListener("click", () => selectYear(y));
      UI.cell(tr, y); UI.cell(tr, tonnes(sp.pdu_t[i])); UI.cell(tr, tonnes(sp.distributed_t[i]));
      UI.cell(tr, tonnes(sp.left_t[i])); UI.cell(tr, f0(sp.pieces_total[i])); UI.cell(tr, tonnes(sp.biomass_t[i]));
      UI.cell(tr, sp.biomass_t[i] ? pct(sp.pdu_t[i] / sp.biomass_t[i]) : "—"); UI.cell(tr, sp.iterations[i]);
      UI.cell(tr, sp.stop_reason[i], "text");
      tb2.appendChild(tr);
    });
    tt.appendChild(tb2);
    UI.footer($("footer-info"), d);
  }

  load();
})();
