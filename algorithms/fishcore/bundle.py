"""
Исходные данные водоёма из наборов данных FishStock в том виде, в каком их читал
исходный проект из data_catch/*.py (FishProps, таблица уловов года, возрастная проба, данные НПЦ).

Таблица набора (data.json сервиса «Входные данные»):
    {"columns": [...], "species": [коды видов], "rows": [{...}]}

Правила восстановления (проверяются тестом сверки с исходными .py):
- виды внутри ядра называются по-русски (как в исходных данных) — по справочнику видов;
- столбец вида попадает в таблицу года, только если за год у вида есть хотя бы одно значение
  (в исходных файлах неучтённый за год вид просто отсутствовал);
- пустое значение → NaN («вид не учитывался»), ноль остаётся нулём;
- порядок видов в свойствах — порядок строк набора «Биологические параметры видов».
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

GEAR_KIND_RU = {"seine": "невод", "net": "сеть"}


def _f(v):
    return np.nan if v is None else float(v)


@dataclass
class Bundle:
    waterbody: str
    tables: dict[str, dict]                  # код типа набора → таблица
    species_names: dict[str, str]            # код вида → название (рус.)
    gear_kinds: dict[str, str]               # код орудия → seine | net
    sources: dict = field(default_factory=dict)   # код типа → {"dataset_id", "version"}

    def require(self, *codes):
        missing = [c for c in codes if c not in self.tables]
        if missing:
            raise ValueError("Нет наборов данных: " + ", ".join(missing))

    def ru(self, code: str) -> str:
        return self.species_names.get(code, code)

    # ------------------------------------------------------------------ свойства видов
    def fish_props(self):
        from .data_source import FishProps
        self.require("species_props", "yearly_conditions", "mean_weights")
        sp = self.tables["species_props"]["rows"]
        yc = self.tables["yearly_conditions"]["rows"]
        names = [self.ru(r["species"]) for r in sp]
        weights = {}
        mw = self.tables["mean_weights"]
        for code in mw.get("species", []):
            rows = [r for r in mw["rows"] if r.get(code) is not None]
            if not rows:
                continue
            df = pd.DataFrame({"age": [r["age"] for r in rows], "year": [r["year"] for r in rows],
                               "w": [float(r[code]) for r in rows]})
            w = df.pivot(index="age", columns="year", values="w").sort_index()
            w.columns = [int(c) for c in w.columns]
            weights[self.ru(code)] = w.astype(float)

        def by(key, cast=float):
            return {n: (cast(r[key]) if r.get(key) is not None else None) for n, r in zip(names, sp)}

        return FishProps(
            lake_area_km2={int(r["year"]): _num(r["lake_area_km2"]) for r in yc},
            net_hours={int(r["year"]): _num(r["net_hours"]) for r in yc},
            net_length={int(r["year"]): _num(r["net_length_m"]) for r in yc},
            cruise_speed=by("v_cr"),
            k_net=by("k_net"),
            k_seine=by("k_seine"),
            m0=by("m0", int), m1=by("m1", int), m2=by("m2", int),
            is_predator={n: int(bool(r["is_predator"])) for n, r in zip(names, sp)},
            fecundity={n: (_num(r["fecundity_min"]), _num(r["fecundity_max"])) for n, r in zip(names, sp)},
            fry_density=by("fry_density"),
            weights=weights,
        )

    # ------------------------------------------------------------------ уловы и пробы
    def catch_years(self) -> list[int]:
        self.require("catches", "age_samples")
        cy = {int(r["year"]) for r in self.tables["catches"]["rows"]}
        sy = {int(r["year"]) for r in self.tables["age_samples"]["rows"]}
        return sorted(cy & sy)

    def year(self, year: int):
        t = self.tables["catches"]
        rows = [r for r in t["rows"] if int(r["year"]) == year]
        present = [c for c in t.get("species", []) if any(r.get(c) is not None for r in rows)]
        data = {
            "Date": [_ddmmyyyy(r["date"]) for r in rows],
            "Year": [int(r["year"]) for r in rows],
            "Place": [r.get("place") for r in rows],
            "Instrument": [GEAR_KIND_RU.get(self.gear_kinds.get(r["gear"], r["gear"]), r["gear"]) for r in rows],
            "Instrument_size": [_num(r.get("gear_size_m")) for r in rows],
            "CatchType": [r.get("catch_type") for r in rows],
            # площадь облова у сети не указывается (пусто); в формате исходного ядра — 0 (используется только для невода)
            "Area": [0.0 if r.get("area_ha") is None else _f(r.get("area_ha")) for r in rows],
        }
        for c in present:
            data[self.ru(c)] = [_f(r.get(c)) for r in rows]
        catches = pd.DataFrame(data)

        s = self.tables["age_samples"]
        srows = sorted((r for r in s["rows"] if int(r["year"]) == year), key=lambda r: r["age"])
        sp = [c for c in s.get("species", []) if any(r.get(c) is not None for r in srows)]
        sample = pd.DataFrame({self.ru(c): [_f(r.get(c)) for r in srows] for c in sp},
                              index=pd.Index([int(r["age"]) for r in srows], name="age"))
        return catches, sample.astype(float)

    def npc(self):
        out = []
        for code in ("npc_stock", "npc_pdu"):
            t = self.tables.get(code)
            if not t:
                out.append(None)
                continue
            rows = sorted(t["rows"], key=lambda r: r["year"])
            df = pd.DataFrame({self.ru(c): [_f(r.get(c)) for r in rows] for c in t.get("species", [])},
                              index=pd.Index([int(r["year"]) for r in rows], name="Id"))
            out.append(df.astype(float))
        return tuple(out)


def _num(v):
    if v is None:
        return None
    f = float(v)
    return int(f) if f.is_integer() else f


def _ddmmyyyy(iso: str) -> str:
    y, m, d = str(iso)[:10].split("-")
    return f"{d}.{m}.{y}"
