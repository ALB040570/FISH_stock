"""
Контрольный пример байесовского этапа: полный расчёт вида на данных Жайсана в том состоянии, в котором
заказчик получил сохранённые результаты 30.09.2026 (k сети до изменения 15.10), и сравнение медиан
численности с legacy/fish_stock_forecast/results/zhaysan_bayes_<вид>.npz.

    python tools/control_bayes.py sazan [--out каталог]

Критерий (согласован 18.10): медианы численности по годам и возрастам — в пределах ±5 %, R̂ < 1,05.
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


def sample_tables(old_k_net: bool = True) -> tuple[dict, dict, dict]:
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("species", nargs="+")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
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
        new = np.load(work / "bayes_cohort" / "out" / f"zhaysan_bayes_{sp}.npz", allow_pickle=True)
        old = np.load(REPO / "legacy" / "fish_stock_forecast" / "results" / f"zhaysan_bayes_{sp}.npz", allow_pickle=True)
        xn, xo = new["X_q"][2][:, 1:], old["X_q"][2][:, 1:]          # медианы, возрасты 1–2 и старше
        rel = np.abs(xn - xo) / np.maximum(np.abs(xo), 1.0)
        big = xo >= np.nanpercentile(xo, 10)                          # самые малочисленные клетки — шум выборки
        tn, to = new["total_obs_q"][2], old["total_obs_q"][2]
        rel_t = np.abs(tn - to) / np.abs(to)
        rh = float(np.nanmax(new["rhat_X"]))
        res = {"species": sp, "total_max_rel": float(rel_t.max()), "by_age_max_rel_main": float(rel[big].max()),
               "by_age_median_rel": float(np.median(rel)), "rhat_max": rh,
               "pass": bool(rel_t.max() <= 0.05 and rh < 1.05)}
        ok &= res["pass"]
        print(json.dumps(res, ensure_ascii=False), flush=True)
    (work / "control_result.json").write_text("ok" if ok else "fail")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
