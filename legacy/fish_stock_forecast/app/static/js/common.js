/* Общие функции страниц: форматирование, плитки, таблицы, подписи возрастных групп. */
const UI = (() => {
  const nf = Charts.nf;
  const fmt = (digits) => (v) => (v === null || v === undefined || Number.isNaN(v) ? "—" : nf(digits).format(v));
  const f0 = fmt(0), f1 = fmt(1), f2 = fmt(2), f3 = fmt(3);
  const thousands = (v) => (v === null || v === undefined ? "—" : nf(v / 1000 >= 100 ? 0 : 1).format(v / 1000));
  const cap = (s) => s[0].toUpperCase() + s.slice(1);

  // Возраст j в данных (less_j) — рыбы в возрасте от j−1 до j лет; подписываем «1–2», «2–3», …
  const AGE_NAMES = { 1: "сеголетки", 2: "двухлетки", 3: "трёхлетки", 4: "четырёхлетки", 5: "пятилетки",
    6: "шестилетки", 7: "семилетки", 8: "восьмилетки", 9: "девятилетки", 10: "десятилетки" };
  const ageLabel = (j) => `${j - 1}–${j}`;
  const ageTitle = (j) => {
    const unit = [2, 3, 4].includes(j % 10) && ![12, 13, 14].includes(j % 100) ? "года" : "лет";
    return `${j - 1}–${j} ${unit}`;
  };
  const ageTip = (j) => `Возраст ${ageTitle(j)}${AGE_NAMES[j] ? ` (${AGE_NAMES[j]})` : ""}`;
  const AGE_AXIS = "Возраст, лет";

  function tile(label, value, sub) {
    const t = document.createElement("div"); t.className = "tile";
    const l = document.createElement("div"); l.className = "tile-label"; l.textContent = label;
    const v = document.createElement("div"); v.className = "tile-value"; v.textContent = value;
    t.append(l, v);
    if (sub) { const s = document.createElement("div"); s.className = "tile-sub"; s.textContent = sub; t.appendChild(s); }
    return t;
  }
  function head(table, cols, textCols = []) {
    const thead = document.createElement("thead"); const tr = document.createElement("tr");
    for (const c of cols) {
      const th = document.createElement("th"); th.textContent = c;
      if (textCols.includes(c)) th.className = "text";
      tr.appendChild(th);
    }
    thead.appendChild(tr); table.appendChild(thead);
  }
  function cell(tr, text, cls) {
    const td = document.createElement("td"); td.textContent = text; if (cls) td.className = cls; tr.appendChild(td);
    return td;
  }
  function segmented(container, items, current, onPick) {
    container.replaceChildren();
    for (const it of items) {
      const b = document.createElement("button");
      b.textContent = it.label; b.className = it.value === current ? "on" : "";
      b.addEventListener("click", () => onPick(it.value));
      container.appendChild(b);
    }
  }
  function yearSelect(select, years, current) {
    select.replaceChildren();
    for (const y of years) {
      const o = document.createElement("option"); o.value = y; o.textContent = y;
      if (y === current) o.selected = true; select.appendChild(o);
    }
  }
  function note(el, parts) {
    if (!parts.length) { el.hidden = true; return; }
    el.replaceChildren();
    const icon = document.createElement("span"); icon.className = "icon"; icon.textContent = "⚠";
    const text = document.createElement("span"); text.textContent = "Обратите внимание: " + parts.join("; ") + ".";
    el.append(icon, text); el.hidden = false;
  }
  function footer(el, d) {
    const info = [`Расчёт: ${d.computed_at}`];
    if (d.seine_computed_at) info.push(`уловистость невода от ${d.seine_computed_at}`);
    info.push(`исходные данные: ${d.source_dir}`);
    const s = d.saved || {};
    if (s.nc_files) info.push(`записано .nc: ${s.nc_files}`);
    if (s.nc_error) info.push(`.nc не записаны: ${s.nc_error}`);
    if (s.error) info.push(`ошибка записи: ${s.error}`);
    if (d.old_error) info.push(`прежние результаты не прочитаны: ${d.old_error}`);
    el.textContent = info.join(" · ");
  }
  async function fetchJSON(url, method = "GET") {
    const resp = await fetch(url, { method });
    if (!resp.ok) throw new Error(`${resp.status} ${await resp.text()}`);
    return resp.json();
  }
  // Вид из адреса страницы (?species=лещ или ?species=lesh) — для переходов со страницы «Обзор»
  const TOKENS = { lesh: "лещ", sudak: "судак", okun: "окунь", plotva: "плотва", shuka: "щука", sazan: "сазан", karas: "карась", yaz: "язь" };
  function initialSpecies(list, fallback) {
    const p = new URLSearchParams(location.search).get("species");
    const sp = p ? (TOKENS[p] || p) : null;
    return sp && list.includes(sp) ? sp : (fallback ?? list[0]);
  }
  return { f0, f1, f2, f3, thousands, cap, ageLabel, ageTitle, ageTip, AGE_AXIS, tile, head, cell, segmented, yearSelect, note, footer,
    fetchJSON, initialSpecies };
})();

/* Общие элементы каркаса: стрелки года, текущий выбор в заголовке, меню на узком экране */
(() => {
  const $ = (id) => document.getElementById(id);
  const sel = $("year-select"), tabs = $("species-tabs"), ctx = $("page-ctx"), yf = $("year-field");

  function syncYear() {
    if (!sel) return;
    const n = sel.options.length;
    if (yf) yf.hidden = n === 0;
    document.querySelectorAll(".ys-btn").forEach((b) => {
      const step = +b.dataset.step;
      b.disabled = n === 0 || (step < 0 ? sel.selectedIndex <= 0 : sel.selectedIndex >= n - 1);
    });
  }
  function syncTitle() {
    if (!ctx) return;
    const on = tabs && tabs.querySelector("button.on");
    const sp = on ? on.textContent.replace(/\s+—$/, "").trim() : "";
    const yr = sel && sel.options.length && !(yf && yf.hidden) ? sel.value : "";
    const parts = [sp, yr].filter(Boolean);
    ctx.textContent = parts.length ? ` — ${parts.join(", ")}` : "";
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest(".ys-btn");
    if (!b || !sel) return;
    const i = sel.selectedIndex + (+b.dataset.step);
    if (i < 0 || i >= sel.options.length) return;
    sel.selectedIndex = i;
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  });
  if (sel) {
    sel.addEventListener("change", () => { syncYear(); syncTitle(); });
    new MutationObserver(() => { syncYear(); syncTitle(); }).observe(sel, { childList: true, subtree: true, attributes: true });
  }
  if (tabs) new MutationObserver(syncTitle).observe(tabs, { childList: true, subtree: true, attributes: true });
  syncYear(); syncTitle();

  // меню на узком экране
  const side = $("side"), back = $("side-backdrop"), btn = $("menu-btn");
  const setMenu = (open) => {
    if (!side) return;
    side.classList.toggle("open", open);
    if (back) back.hidden = !open;
    if (btn) btn.setAttribute("aria-expanded", String(open));
  };
  if (btn) btn.addEventListener("click", () => setMenu(!side.classList.contains("open")));
  if (back) back.addEventListener("click", () => setMenu(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setMenu(false); });
})();
