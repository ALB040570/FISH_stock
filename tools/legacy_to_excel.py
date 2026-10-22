"""
Перенос исходных данных заказчика (legacy/data_catch/*.py) в Excel-файлы по шаблонам FishStock.

    python tools/legacy_to_excel.py [--src legacy/data_catch] [--waterbody zhaysan] [--out samples/zhaysan]

Создаёт по файлу на тип набора данных (catches.xlsx, age_samples.xlsx, ...). Значения переносятся
без изменений; пропуски (вид не учитывался) остаются пустыми ячейками.
"""
from __future__ import annotations

import argparse
import math
import re
import runpy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "libs" / "fishcommon"), str(REPO / "services" / "data_admin"),
                str(REPO / "services" / "data_model")]
from app import tables  # noqa: E402  (services/data_admin/app)

sys.path.remove(str(REPO / "services" / "data_admin"))
for m in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
    del sys.modules[m]
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("seed_defs", REPO / "services/data_model/app/seed_defs.py")
seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed)

SP_CODE = {ru: code for code, ru, *_ in seed.SPECIES}
SP_CODE.update(seed.SPECIES_ALIASES)           # «т_лоб», «беламур» … — написания в файлах заказчика
SP_RU = {code: ru for code, ru, *_ in seed.SPECIES}
SPECIES = [{"code": c, "name_ru": ru, "name_kk": kk} for c, ru, kk, *_ in seed.SPECIES]
DT = {t["code"]: t for t in seed.DATASET_TYPES}
SKIPPED: list[str] = []


def _v(x):
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    if hasattr(x, "item"):
        x = x.item()
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


def _species_of(cols):
    out = []
    for c in cols:
        if c in SP_CODE:
            out.append(SP_CODE[c])
        elif c not in ("LessAge", "age", "Id", "Date", "Year", "Place", "Instrument", "Instrument_size",
                       "CatchType", "Area"):
            raise SystemExit(f"Неизвестный вид в исходных данных: {c} — добавьте в seed_defs.SPECIES")
    return out


def convert(src: Path, wb: str) -> dict[str, tuple[list[str], list[dict]]]:
    out = {}
    years = sorted(int(re.search(r"_(\d{4})\.py$", p.name).group(1)) for p in src.glob(f"{wb}_catch_*.py"))
    catches, samples, sp_c, sp_s = [], [], [], []
    for y in years:
        m = runpy.run_path(str(src / f"{wb}_catch_{y}.py"))
        df = m[f"{wb}_catch_{y}"]
        sp = _species_of(df.columns)
        sp_c += [s for s in sp if s not in sp_c]
        ru = {SP_CODE[c]: c for c in df.columns if c in SP_CODE}
        for _, r in df.iterrows():
            if r["Instrument"] not in ("невод", "сеть"):
                # исходный код учитывает только «невод» и «сеть»; такие ловы в расчёт не входили
                SKIPPED.append(f"{wb}_catch_{y}.py: лов {r['Date']}, {r['Place']}, орудие «{r['Instrument']}» — "
                               "не невод и не сеть, в расчёт не входит; не перенесён")
                continue
            d, mth, yr = str(r["Date"]).split(".")
            row = {"year": int(r["Year"]), "date": f"{yr}-{mth}-{d}", "place": r["Place"],
                   "gear": r["Instrument"], "gear_desc": None, "gear_size_m": _v(r["Instrument_size"]),
                   "area_ha": _v(r["Area"]), "catch_type": r["CatchType"]}
            for code, col in ru.items():
                row[code] = _v(r[col])
            catches.append(row)
        key = f"qty_treated_fish_{y}" if f"qty_treated_fish_{y}" in m else next(k for k in m if k.startswith("qty_treated_fish_"))
        q = m[key]
        sps = _species_of(q.columns)
        sp_s += [s for s in sps if s not in sp_s]
        for _, r in q.iterrows():
            row = {"year": y, "age": int(r["age"])}
            for c in q.columns:
                if c in SP_CODE:
                    row[SP_CODE[c]] = _v(r[c])
            samples.append(row)
    out["catches"] = (sp_c, catches)
    out["age_samples"] = (sp_s, samples)

    p = runpy.run_path(str(src / f"{wb}_fish_prop.py"))
    props = []
    for ru, m1 in p["m1_dict"].items():
        fmin, fmax = p["fecundity_dict"][ru]
        props.append({"species": SP_RU[SP_CODE[ru]], "m0": p["m0_dict"][ru], "m1": m1, "m2": p["m2_dict"][ru],
                      "v_cr": p["v_cr_dict"][ru], "k_net": p["k_catchability_1"][ru], "k_seine": p["k_catchability_2"][ru],
                      "is_predator": bool(p["fish_is_predator_dict"][ru]), "fecundity_min": fmin, "fecundity_max": fmax,
                      "fry_density": p["fish_density_dict"][ru]})
    out["species_props"] = ([], props)
    yrs = sorted(p["square_by_years"])
    out["yearly_conditions"] = ([], [{"year": y, "lake_area_km2": _v(p["square_by_years"][y]),
                                      "net_length_m": _v(p["net_length"][y]), "net_hours": _v(p["time_net_hour"][y])}
                                     for y in yrs])
    weights: dict[tuple[int, int], dict] = {}
    sp_w = []
    for ru, var in p["fish_list_dict"].items():
        code = SP_CODE[ru]
        sp_w.append(code)
        df = p[var]
        for _, r in df.iterrows():
            for col in df.columns:
                if isinstance(col, int):
                    weights.setdefault((col, int(r["age"])), {"year": col, "age": int(r["age"])})[code] = _v(r[col])
    out["mean_weights"] = (sp_w, [weights[k] for k in sorted(weights)])

    npc_path = src / f"{wb}_npc_assessment.py"
    if npc_path.exists():
        n = runpy.run_path(str(npc_path))
        for name, code in (("data_stock_npc", "npc_stock"), ("data_pdu_npc", "npc_pdu")):
            df = n[name]
            sps = _species_of(df.columns)
            rows = []
            for _, r in df.iterrows():
                row = {"year": int(r["Id"])}
                for c in df.columns:
                    if c in SP_CODE:
                        row[SP_CODE[c]] = _v(r[c])
                rows.append(row)
            out[code] = (sps, rows)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(REPO / "legacy" / "data_catch"))
    ap.add_argument("--waterbody", default="zhaysan")
    ap.add_argument("--out", default=str(REPO / "samples" / "zhaysan"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    gear_names = ["невод", "сеть"]
    sp_names = [s["name_ru"] for s in SPECIES]
    for code, (sp_codes, rows) in convert(Path(a.src), a.waterbody).items():
        sp = [s for s in SPECIES if s["code"] in sp_codes]
        sp.sort(key=lambda s: sp_codes.index(s["code"]))
        data = tables.build_template(DT[code], sp, {"gears": gear_names, "species": sp_names}, "ru", rows=rows)
        (out / f"{code}.xlsx").write_bytes(data)
        print(f"{code}.xlsx: {len(rows)} строк, видов {len(sp)}")
    for msg in SKIPPED:
        print("ПРОПУЩЕНО:", msg)


if __name__ == "__main__":
    main()
