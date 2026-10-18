"""
Этап 2 для веб-интерфейса: уловистость сети и запас по уловам.

Результат зависит от уловистости невода (этап 1): если её пересчитали,
этап 2 пересчитывается автоматически при следующем обращении.
"""
from __future__ import annotations

import io
import threading
from datetime import datetime

import numpy as np
import pandas as pd

from core import cache, config
from core.data_source import load_fish_props
from core.ages import age_label, age_title
from core.export_nc import GEAR_TOKEN, load_old_cube, save_pdu, save_stage2
from core.pdu_npc import compute_pdu
from core.stock import GEARS, MEAN, METHODS, VARIANTS, METHOD_TITLES, VARIANT_TITLES, compute_stock
from app import services as seine_services
from app.services import _arr, _num

_lock = threading.RLock()
_state: dict = {"stock": None, "net_c": None, "pdu": None, "seine_stamp": None, "computed_at": None,
                "saved": {}, "old_net": None, "old_yearly": {}, "old_error": None}


STAGE23_KEYS = ("stock", "net_c", "pdu", "seine_stamp", "computed_at", "saved", "old_net", "old_yearly", "old_error")


def _fingerprint() -> str:
    return cache.fingerprint("stage23", seine_services._state["computed_at"])


def recalculate():
    """Пересчитать этапы 2–3 (запас по уловам, ПДУ по возрастам), сохранить результаты и кэш."""
    with _lock:
        seine_c = seine_services.get_result()
        with cache.timed("этап 2 (запас по уловам): расчёт"):
            res, net_c, _ = compute_stock(seine_c=seine_c)
        with cache.timed("этап 3 (ПДУ по возрастам): расчёт"):
            pdu = compute_pdu(res, load_fish_props())
        with cache.timed("этапы 2–3: запись файлов .nc и .csv в results"):
            try:
                saved = save_stage2(res, net_c)
                saved_pdu = save_pdu(pdu)
                if saved_pdu.get("nc_files") and saved.get("nc_files"):
                    saved["nc_files"] = str(int(saved["nc_files"]) + int(saved_pdu["nc_files"]))
            except Exception as e:
                saved = {"error": str(e)}
        old_net, old_yearly, old_error = None, {}, None
        with cache.timed("этап 2: чтение старых файлов data_stock"):
            try:
                old_net = load_old_cube(f"{res.waterbody}_catchability_net_3d.nc")
                for gear in GEARS:
                    for v in VARIANTS:
                        for meth in METHODS:
                            cube = load_old_cube(f"{res.waterbody}_yearly_stock_{GEAR_TOKEN[gear]}_{v}_{meth}_3d.nc")
                            if cube is not None:
                                old_yearly[(gear, v, meth)] = cube
            except Exception as e:
                old_error = str(e)
        _state.update(stock=res, net_c=net_c, pdu=pdu, seine_stamp=seine_services._state["computed_at"],
                      computed_at=datetime.now().strftime("%d.%m.%Y %H:%M:%S"), saved=saved,
                      old_net=old_net, old_yearly=old_yearly, old_error=old_error)
        cache.save("stage23", _fingerprint(), {k: _state[k] for k in STAGE23_KEYS})
        return res, net_c


def get_stage2():
    """Результат этапов 2–3: из памяти, из кэша на диске или новым расчётом.

    Если уловистость невода (этап 1) пересчитали, этапы 2–3 пересчитываются.
    """
    with _lock:
        seine_services.get_result()
        stamp = seine_services._state["computed_at"]
        if _state["stock"] is None or _state["seine_stamp"] != stamp:
            obj = cache.load("stage23", _fingerprint()) if _state["stock"] is None else None
            if obj and obj.get("seine_stamp") == stamp:
                _state.update(obj)
                cache.log(f"этапы 2–3 взяты из кэша (расчёт от {_state['computed_at']})")
            else:
                recalculate()
        return _state["stock"], _state["net_c"]


def get_pdu():
    get_stage2()
    return _state["pdu"]


def _footer():
    return {"computed_at": _state["computed_at"], "saved": {k: str(v) for k, v in _state["saved"].items()},
            "old_error": _state["old_error"], "source_dir": str(config.SOURCE_PROJECT_DIR),
            "seine_computed_at": _state["seine_stamp"]}


# ---------------------------------------------------------------------------
# Уловистость сети
# ---------------------------------------------------------------------------
def net_payload() -> dict:
    res, net_c = get_stage2()
    props = load_fish_props()
    old = _state["old_net"]
    sigma = res.sigma["with_ages"]
    fits = {}
    for (fish, year), r in net_c.fits.items():
        yi, si = res.years.index(year), res.species.index(fish)
        idx = [int(np.where(res.ages == a)[0][0]) for a in r.ages]
        old_c = [_num(old[(fish, year)].get(int(a))) for a in r.ages] if old and (fish, year) in old else None
        p = r.parabola
        fits.setdefault(fish, {})[str(year)] = {
            "ages": _arr(r.ages.astype(int)), "observed": _arr(r.observed), "c": _arr(r.catchability),
            "c_old": old_c, "sigma": _arr(sigma[yi, si, idx]),
            "peak": _num(p.peak), "c0": _num(p.c0), "a1": _num(p.a1), "a2": _num(p.a2),
            "c_mean": _num(r.c_mean), "m0": r.m0, "m1": r.m1,
            "n_sample": r.n_sample, "total_catch": _num(r.total_catch), "n_hauls": r.n_hauls,
            "source": r.source, "status": r.status, "observed_is_catch": r.source.startswith("годовой улов"),
            "hours": _num(float(props.net_hours[year])), "net_length": _num(float(props.net_length[year])),
            "speed": _num(float(props.cruise_speed[fish]) * 3600),
        }
    return {"waterbody": res.waterbody, "years": res.years, "species": res.species,
            "c_lower": config.NET_C_LOWER, "c_upper": config.NET_C_UPPER,
            "fits": fits, "old_available": old is not None, **_footer()}


def net_excel() -> bytes:
    res, net_c = get_stage2()
    cube = net_c.cube_frame().pivot_table(index=["вид", "год"], columns="возраст", values="c", sort=False)
    cube = cube.reindex(columns=[c for c in (age_label(a) for a in res.ages) if c in cube.columns])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        net_c.params_frame().to_excel(xw, sheet_name="Параметры парабол", index=False)
        cube.to_excel(xw, sheet_name="Коэффициенты c(вид,год,возр)")
        old = _state["old_net"]
        if old:
            rows = []
            for (fish, year), r in net_c.fits.items():
                for a, c in zip(r.ages.astype(int), r.catchability):
                    c_old = old.get((fish, year), {}).get(int(a))
                    rows.append({"вид": fish, "год": year, "возраст": age_label(a), "c парабола": c,
                                 "c прежний": c_old, "разница": None if c_old is None else c - c_old})
            pd.DataFrame(rows).to_excel(xw, sheet_name="Сравнение с прежними", index=False)
        _autowidth(xw)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Запас по уловам
# ---------------------------------------------------------------------------
def _old_totals(res, gear, v, meth):
    """Годовые суммы (группы 2..m1) из прежнего файла или None."""
    cube = _state["old_yearly"].get((gear, v, meth))
    if not cube:
        return None
    out = np.full((len(res.years), len(res.species)), np.nan)
    for yi, y in enumerate(res.years):
        for si, s in enumerate(res.species):
            vals = cube.get((s, y))
            if vals:
                arr = np.array([vals.get(int(a), np.nan) for a in range(2, res.m1[s] + 1)], float)
                if not np.all(np.isnan(arr)):
                    out[yi, si] = np.nansum(arr)
    return out


def _ints(a):
    """Запас в штуках: округление до целых, NaN -> None."""
    return [None if not np.isfinite(v) else int(round(v)) for v in np.asarray(a, float).tolist()]


def stock_payload() -> dict:
    res, _ = get_stage2()
    species = {}
    for si, fish in enumerate(res.species):
        m1 = res.m1[fish]
        age_idx = [i for i, a in enumerate(res.ages) if 2 <= a <= m1]
        block = {"ages": [int(res.ages[i]) for i in age_idx], "variants": {}}
        for v in VARIANTS:
            vb = {}
            for meth in METHODS:
                mb = {"totals": {}, "by_age": {}, "old_totals": {}}
                for g in (*GEARS, MEAN):
                    mb["totals"][g] = _ints(res.yearly_total(g, v, meth)[:, si])
                    mb["by_age"][g] = [_ints(res.yearly[(g, v, meth)][yi, si, age_idx]) for yi in range(len(res.years))]
                for g in GEARS:
                    ot = _old_totals(res, g, v, meth)
                    mb["old_totals"][g] = _ints(ot[:, si]) if ot is not None else None
                vb[meth] = mb
            # оценки по ловам: значения по порядку ловов из payload["hauls"] (None — вид не учитывался)
            vb["hauls"] = {g: _ints(res.per_haul_total(g, v)[:, si]) for g in GEARS}
            block["variants"][v] = vb
        counts = {g: _arr(res.catches[g].yearly_count()[:, si]) for g in GEARS}
        block["n_hauls"] = counts
        block["npc"] = _ints(res.npc_stock[:, si]) if res.npc_stock is not None else None
        species[fish] = block
    hauls = {}
    for g in GEARS:
        m = res.catches[g].meta
        hauls[g] = {"year": m["Year"].astype(int).tolist(), "date": m["Date"].astype(str).tolist(),
                    "place": m["Place"].astype(str).tolist(), "type": m["CatchType"].astype(str).tolist()}
    return {"waterbody": res.waterbody, "years": res.years, "species_list": res.species, "species": species,
            "hauls": hauls,
            "gears": {"net": config.GEAR_NET, "seine": config.GEAR_SEINE, "mean": MEAN},
            "variant_titles": VARIANT_TITLES, "method_titles": METHOD_TITLES,
            "combine_how": config.COMBINE_GEARS, "net_formula": config.NET_STOCK_FORMULA,
            "old_available": bool(_state["old_yearly"]), **_footer()}


def stock_excel() -> bytes:
    res, _ = get_stage2()
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        res.totals_frame().to_excel(xw, sheet_name="Годовой запас (итоги)", index=False)
        for v in VARIANTS:
            rows = []
            for g in (*GEARS, MEAN):
                cube = res.yearly[(g, v, "on_stock")]
                for si, fish in enumerate(res.species):
                    for yi, year in enumerate(res.years):
                        row = {"орудие": g, "вид": fish, "год": year}
                        for ai, a in enumerate(res.ages):
                            if 2 <= a <= res.m1[fish]:
                                row[f"возраст {age_label(a)}"] = cube[yi, si, ai]
                        rows.append(row)
            name = "По возрастам, c по возр." if v == "with_ages" else "По возрастам, c средняя"
            pd.DataFrame(rows).to_excel(xw, sheet_name=name, index=False)
        for g in GEARS:
            hc = res.catches[g]
            df = hc.meta.copy()
            tot = res.per_haul_total(g, "with_ages")
            for si, fish in enumerate(res.species):
                df[f"{fish}, запас шт"] = tot[:, si]
            df.to_excel(xw, sheet_name=f"Оценки по ловам ({g})", index=False)
        _autowidth(xw)
    return buf.getvalue()


def _autowidth(xw):
    for ws in xw.book.worksheets:
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 40)


# ---------------------------------------------------------------------------
# ПДУ НПЦ по возрастам
# ---------------------------------------------------------------------------
def pdu_payload() -> dict:
    pdu = get_pdu()
    dist = pdu.distributed_t()
    bio = pdu.fishable_biomass_t()
    expl = pdu.exploitation()
    species = {}
    for si, fish in enumerate(pdu.species):
        idx = [i for i, a in enumerate(pdu.ages) if 2 <= a <= pdu.m1[fish]]
        species[fish] = {
            "m0": pdu.m0[fish], "m1": pdu.m1[fish],
            "ages": [int(pdu.ages[i]) for i in idx],
            "weight_filled": [bool(pdu.weight_filled[si, i]) for i in idx],
            "pdu_t": _arr(pdu.pdu_t[:, si]), "distributed_t": _arr(dist[:, si]), "left_t": _arr(pdu.left_t[:, si]),
            "pieces_total": _ints(pdu.pieces[:, si].sum(axis=1)), "biomass_t": _arr(bio[:, si]),
            "iterations": [int(v) for v in pdu.iterations[:, si]],
            "stop_reason": [pdu.stop_reason[yi][si] for yi in range(len(pdu.years))],
            "by_year": [{
                "stock": _ints(pdu.stock[yi, si, idx]),
                "weight": _arr(pdu.weights[yi, si, idx]),
                "pieces": _ints(pdu.pieces[yi, si, idx]),
                "tonnes": _arr(pdu.pieces[yi, si, idx] * pdu.weights[yi, si, idx] / 1e6),
                "exploitation": _arr(expl[yi, si, idx]),
                "capped": [bool(v) for v in pdu.capped[yi, si, idx]],
            } for yi in range(len(pdu.years))],
        }
    return {"waterbody": pdu.waterbody, "years": pdu.years, "species_list": pdu.species, "species": species,
            "cap": config.PDU_CAP, "net_formula": config.NET_STOCK_FORMULA, **_footer()}


def pdu_excel() -> bytes:
    pdu = get_pdu()
    buf = io.BytesIO()
    expl = pdu.exploitation()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pdu.summary_frame().to_excel(xw, sheet_name="Итоги по годам", index=False)
        rows = []
        for si, fish in enumerate(pdu.species):
            for yi, year in enumerate(pdu.years):
                for ai, a in enumerate(pdu.ages):
                    if not (2 <= a <= pdu.m1[fish]):
                        continue
                    rows.append({
                        "вид": fish, "год": year, "возраст": age_title(a),
                        "окончательный запас, шт": pdu.stock[yi, si, ai], "средний вес, г": pdu.weights[yi, si, ai],
                        "вес взят от младшего возраста": bool(pdu.weight_filled[si, ai]),
                        "ПДУ, шт": pdu.pieces[yi, si, ai], "ПДУ, т": pdu.pieces[yi, si, ai] * pdu.weights[yi, si, ai] / 1e6,
                        "доля изъятия": expl[yi, si, ai], "срабатывало ограничение 75 %": bool(pdu.capped[yi, si, ai]),
                    })
        pd.DataFrame(rows).to_excel(xw, sheet_name="По возрастам", index=False)
        _autowidth(xw)
    return buf.getvalue()
