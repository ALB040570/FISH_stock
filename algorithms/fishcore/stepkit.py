"""
Общее для пакетов алгоритмов FishStock: набор данных водоёма из контекста шага,
применение неизменяемых параметров методики к fishcore.config, проверка наличия данных.
"""
from __future__ import annotations

from . import config
from .bundle import Bundle

# Неизменяемые параметры методики: имя в манифесте → атрибут fishcore.config
FIXED_CONFIG = (
    "SEINE_MIN_AGE", "SEINE_C_LOWER", "SEINE_C_LOWER_FIRST", "SEINE_C_UPPER", "SEINE_MIN_SAMPLE",
    "NET_MIN_AGE", "NET_END_LEFT", "NET_END_RIGHT", "NET_C_LOWER", "NET_C_UPPER", "NET_MIN_SAMPLE",
    "HECTARE_M2", "KM2_M2", "NPC_STOCK_MULTIPLIER", "NET_STOCK_FORMULA", "COMBINE_GEARS",
    "PDU_CAP", "PDU_MAX_ITER", "PDU_TOL_G", "PDU_FREE_STOCK_TOL_G",
)


class DataMissing(Exception):
    pass


def apply_fixed(params: dict) -> None:
    for k in FIXED_CONFIG:
        if k in params and params[k] is not None:
            cur = getattr(config, k)
            v = params[k]
            setattr(config, k, type(cur)(v) if not isinstance(cur, str) else str(v))


def bundle(ctx, *required: str) -> Bundle:
    missing = [c for c in required if c not in ctx.tables]
    if missing:
        from fishrunner import UserError
        titles = {"catches": "Уловы по ловам", "age_samples": "Возрастные пробы", "mean_weights": "Средний вес",
                  "species_props": "Биологические параметры видов", "yearly_conditions": "Условия по годам",
                  "npc_stock": "Оценка запаса НПЦ", "npc_pdu": "ПДУ НПЦ"}
        raise UserError("Для водоёма не загружены наборы данных: " + ", ".join(titles.get(m, m) for m in missing))
    config.WATERBODY = ctx.water_body
    config.RESULTS_DIR = ctx.out_dir
    return Bundle(ctx.water_body, ctx.tables, ctx.species_names, ctx.gear_kinds, ctx.dataset_sources)


def species_code(ctx, name_ru: str) -> str:
    for code, ru in ctx.species_names.items():
        if ru == name_ru:
            return code
    return name_ru
