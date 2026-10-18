"""
Прослойка между расчётным ядром (core) и веб-интерфейсом.

Результаты расчёта хранятся в памяти процесса; при первом обращении
расчёт выполняется и сохраняется в папку results/.
"""
from __future__ import annotations

import io
import threading
from datetime import datetime

import numpy as np
import pandas as pd

from core import cache, config
from core.ages import age_label
from core.catchability_seine import (
    SeineCatchability, compute_seine_catchability, load_old_cube, save_results,
)

_lock = threading.RLock()
_state: dict = {"result": None, "old": None, "old_error": None, "computed_at": None, "saved": {}}


def _num(x):
    """numpy -> обычные числа для JSON; NaN -> None."""
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else round(float(x), 6)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def _arr(a):
    return [_num(v) for v in np.asarray(a).tolist()]


STAGE1_KEYS = ("result", "old", "old_error", "computed_at", "saved")


def _fingerprint() -> str:
    return cache.fingerprint("stage1")


def recalculate() -> SeineCatchability:
    """Пересчитать уловистость невода по исходным данным, сохранить результаты и кэш."""
    with _lock:
        with cache.timed("этап 1 (уловистость невода): расчёт"):
            res = compute_seine_catchability()
        with cache.timed("этап 1: запись файлов в results"):
            try:
                saved = save_results(res)
            except Exception as e:  # расчёт важнее записи: показываем, но не падаем
                saved = {"error": str(e)}
        with cache.timed("этап 1: чтение старых коэффициентов data_stock"):
            try:
                old, old_error = load_old_cube(), None
            except Exception as e:
                old, old_error = None, str(e)
        _state.update(result=res, old=old, old_error=old_error,
                      computed_at=datetime.now().strftime("%d.%m.%Y %H:%M:%S"), saved=saved)
        cache.save("stage1", _fingerprint(), {k: _state[k] for k in STAGE1_KEYS})
        return res


def get_result() -> SeineCatchability:
    """Результат этапа 1: из памяти, из кэша на диске или новым расчётом."""
    if _state["result"] is None:
        with _lock:
            if _state["result"] is None:
                obj = cache.load("stage1", _fingerprint())
                if obj:
                    _state.update(obj)
                    cache.log(f"этап 1 взят из кэша (расчёт от {_state['computed_at']})")
                else:
                    recalculate()
    return _state["result"]


def seine_payload() -> dict:
    """Все данные страницы «Уловистость невода» одним JSON."""
    res = get_result()
    old = _state["old"]
    fits = {}
    for (fish, year), r in res.fits.items():
        old_c = None
        if old is not None and (fish, year) in old:
            old_c = [_num(old[(fish, year)].get(int(a))) for a in r.ages]
        fits.setdefault(fish, {})[str(year)] = {
            "ages": _arr(r.ages.astype(int)),
            "observed": _arr(r.observed),
            "fitted": _arr(r.fitted),
            "weights": _arr(r.weights),
            "c": _arr(r.catchability),
            "c_old": old_c,
            "a": _num(r.fit.a), "j50": _num(r.fit.j50), "j50_rule": _num(r.j50_rule),
            "b": _num(r.fit.b), "Z": _num(r.fit.Z), "r2": _num(r.fit.r2),
            "c_mean": _num(r.c_mean), "m0": r.m0, "m1": r.m1,
            "n_sample": r.n_sample, "total_catch": _num(r.total_catch), "n_hauls": r.n_hauls,
            "source": r.source, "status": r.status,
            "first_lower_active": r.fit.first_lower_active,
            "lower_active": r.fit.lower_active, "upper_active": r.fit.upper_active,
            "observed_is_catch": r.source.startswith("годовой улов"),
        }
    saved = {k: str(v) for k, v in _state["saved"].items()}
    return {
        "waterbody": res.waterbody,
        "years": res.years,
        "species": res.species,
        "c_lower": config.SEINE_C_LOWER,
        "c_lower_first": config.SEINE_C_LOWER_FIRST,
        "c_upper": config.SEINE_C_UPPER,
        "fits": fits,
        "old_available": old is not None,
        "old_error": _state["old_error"],
        "computed_at": _state["computed_at"],
        "saved": saved,
        "source_dir": str(config.SOURCE_PROJECT_DIR),
    }


def seine_excel() -> bytes:
    """Excel: параметры, куб коэффициентов, сравнение со старыми коэффициентами."""
    res = get_result()
    params = res.params_frame()
    cube = res.cube_frame().pivot_table(index=["вид", "год"], columns="возраст", values="c", sort=False)
    labels = [age_label(a) for a in res.all_ages]
    cube = cube.reindex(columns=[c for c in labels if c in cube.columns])
    cube = cube.reindex(pd.MultiIndex.from_product([res.species, res.years], names=["вид", "год"]))

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        params.to_excel(xw, sheet_name="Параметры сигмоид", index=False)
        cube.to_excel(xw, sheet_name="Коэффициенты c(вид,год,возр)")
        old = _state["old"]
        if old is not None:
            rows = []
            for (fish, year), r in res.fits.items():
                for age, c_new in zip(r.ages.astype(int), r.catchability):
                    c_old = old.get((fish, year), {}).get(int(age))
                    rows.append({"вид": fish, "год": year, "возраст": age_label(age),
                                 "c МНК": c_new, "c байес (старый)": c_old,
                                 "разница": None if c_old is None else c_new - c_old})
            pd.DataFrame(rows).to_excel(xw, sheet_name="Сравнение со старыми", index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 45)
    return buf.getvalue()
