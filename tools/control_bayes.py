"""
Контрольный пример байесовского этапа: полный расчёт вида на данных Жайсана (образцы samples/zhaysan) алгоритмами
FishStock и сравнение медиан численности с результатами эталона legacy/fish_stock_forecast/results/zhaysan_bayes_<вид>.npz
(fish_stock_forecast от 22.10.2026, расчёты автора 4 × 1000).

    python tools/control_bayes.py sazan [--out каталог]
    python tools/control_bayes.py --zip run_<id>.zip     # сверить готовый запуск (выгрузка «Все результаты (zip)»)

Сверка выгрузки верна, если данные Жайсана в установке — образцы поставки (samples/zhaysan) без правок.

Критерий (согласован 18.10): суммарная численность по годам — в пределах ±5 %, R̂ < 1,05.
При тех же настройках и seed перенос даёт те же выборки, что эталон (проверено 23.10.2026 на коротком расчёте сазана).
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "algorithms"), str(REPO / "libs" / "fishcommon")]
import build  # noqa: E402
import executor  # noqa: E402

K_NET_2026_09_30 = {"lesh": 0.3, "plotva": 0.35, "sazan": 0.3, "karas": 0.4, "yaz": 0.4, "sudak": 0.25, "okun": 0.35,
                    "shuka": 0.4}


def sample_tables(old_k_net: bool = False) -> tuple[dict, dict, dict]:
    sys.path.insert(0, str(REPO / "services" / "data_admin"))
    from app import tables as T  # noqa: E402
    import importlib.util
    spec = importlib.util.spec_from_file_location("seed_defs", REPO / "services/data_model/app/seed_defs.py")
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    species = [{"code": c, "name_ru": ru, "name_kk": kk} for c, ru, kk, *_ in seed.SPECIES]
    refs = {"species": {}, "gears": {}}
    for s in species:
        for k in (s["code"], s["name_ru"]):
            refs["species"][k.lower()] = s["code"]
    for ent in ("catch_types",):                         # справочники-классификаторы (код, рус., каз., …)
        m = refs.setdefault(ent, {})
        for code, ru, *_ in seed.CLASSIFIERS[ent]:
            m[code] = code
            m[ru.lower()] = code
        for (e, code), names_ in seed.CLASSIFIER_ALIASES.items():
            if e == ent:
                for n in names_.split("\n"):
                    m[n.lower()] = code
    for code, ru, kk, kind in seed.GEARS:
        refs["gears"][code] = code
        refs["gears"][ru] = code
    out = {}
    for dt in seed.DATASET_TYPES:
        f = REPO / "samples" / "zhaysan" / f"{dt['code']}.xlsx"
        sp, raw = T.read_excel(f.read_bytes(), dt, species)
        rows, errors, _ = T.validate_rows(dt, sp, species, raw, refs)
        assert not errors, errors[:3]
        out[dt["code"]] = T.merge_rows(dt, None, rows, sp, "replace")
    if old_k_net:
        for r in out["species_props"]["rows"]:
            r["k_net"] = K_NET_2026_09_30[r["species"]]
    names = {s["code"]: s["name_ru"] for s in species}
    kinds = {c: kind for c, ru, kk, kind in seed.GEARS}
    return out, names, kinds


def compare(sp: str, new_path) -> dict:
    """Медианы численности вида sp (файл npz шага модели) против результатов эталона."""
    new = np.load(new_path, allow_pickle=True)
    old = np.load(REPO / "legacy" / "fish_stock_forecast" / "results" / f"zhaysan_bayes_{sp}.npz", allow_pickle=True)
    xn, xo = new["X_q"][2][:, 1:], old["X_q"][2][:, 1:]          # медианы, возрасты 1–2 и старше
    rel = np.abs(xn - xo) / np.maximum(np.abs(xo), 1.0)
    big = xo >= np.nanpercentile(xo, 10)                          # самые малочисленные клетки — шум выборки
    tn, to = new["total_obs_q"][2], old["total_obs_q"][2]
    rel_t = np.abs(tn - to) / np.abs(to)
    rh = float(np.nanmax(new["rhat_X"]))
    return {"species": sp, "total_max_rel": float(rel_t.max()), "by_age_max_rel_main": float(rel[big].max()),
            "by_age_median_rel": float(np.median(rel)), "rhat_max": rh,
            "pass": bool(rel_t.max() <= 0.05 and rh < 1.05)}


def compare_zip(path: Path) -> bool:
    import io
    import re
    import zipfile
    ok, seen = True, 0
    ref = REPO / "legacy" / "fish_stock_forecast" / "results"
    with zipfile.ZipFile(path) as z:
        for name in sorted(z.namelist()):
            m = re.search(r"bayes_cohort/zhaysan_bayes_([a-z]+)\.npz$", name)
            if not m:
                continue
            sp = m.group(1)
            if not (ref / f"zhaysan_bayes_{sp}.npz").exists():
                print(json.dumps({"species": sp, "note": "у эталона нет результатов"}, ensure_ascii=False))
                continue
            res = compare(sp, io.BytesIO(z.read(name)))
            ok &= res["pass"]
            seen += 1
            print(json.dumps(res, ensure_ascii=False), flush=True)
    if not seen:
        print("в выгрузке нет результатов шага байесовской модели по Жайсану")
        return False
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("species", nargs="*")
    ap.add_argument("--out", default=None)
    ap.add_argument("--zip", default=None, help="выгрузка запуска (zip) — сверить без пересчёта")
    a = ap.parse_args()
    if a.zip:
        sys.exit(0 if compare_zip(Path(a.zip)) else 2)
    if not a.species:
        ap.error("укажите виды или --zip")
    work = Path(a.out or tempfile.mkdtemp(prefix="control_bayes_"))
    work.mkdir(parents=True, exist_ok=True)
    tables, names, kinds = sample_tables()
    (work / "tables.json").write_text(json.dumps(tables, ensure_ascii=False))
    pkgs = {m["code"]: f for m, f in build.builtin()}
    prev = {}
    for code, params in (("seine_catchability", {}), ("stock_by_catch", {}), ("pdu_by_age", {}),
                         ("bayes_cohort", {"mode": "new", "species": a.species})):
        m = json.loads(pkgs[code]["manifest.json"])
        defaults = {p["code"]: p["default"] for p in m["parameters"] if p.get("default") is not None}
        ctx = {"run_id": "control", "step": code, "water_body": "zhaysan", "params": {**defaults, **params},
               "species_names": names, "gear_kinds": kinds, "inputs": {k: str(v / "out") for k, v in prev.items()},
               "tables_path": str(work / "tables.json")}
        d = work / code
        executor.prepare_step(d, pkgs[code], ctx)
        print(f"{code}: запуск", flush=True)
        st = executor.run_step(d)
        print(f"{code}: {st['status']} {st.get('message', '')}", flush=True)
        if st["status"] != "done":
            sys.exit(1)
        prev[code] = d
    ok = True
    for sp in a.species:
        res = compare(sp, work / "bayes_cohort" / "out" / f"zhaysan_bayes_{sp}.npz")
        ok &= res["pass"]
        print(json.dumps(res, ensure_ascii=False), flush=True)
    (work / "control_result.json").write_text("ok" if ok else "fail")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
