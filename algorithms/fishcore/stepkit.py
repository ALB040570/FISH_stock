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
    "NET_MIN_AGE", "NET_END_LEFT_FRAC", "NET_END_RIGHT_FRAC", "NET_C_LOWER_FRAC", "NET_C_UPPER", "NET_MIN_SAMPLE",
    "HECTARE_M2", "KM2_M2", "NPC_STOCK_MULTIPLIER", "NET_STOCK_FORMULA", "COMBINE_GEARS",
    "NET_ZONE0_SUBSTEPS", "NET_PANELS_MODE", "AGE_PSEUDOCOUNT_TOTAL", "AGE_POOL_MIN_SAMPLE", "AGE_POOL_NEIGHBOURS",
    "PDU_CAP", "PDU_MAX_ITER", "PDU_TOL_G", "PDU_FREE_STOCK_TOL_G",
)

TITLES = {"catches": "Уловы по ловам", "age_samples": "Возрастные пробы", "mean_weights": "Средний вес",
          "species_props": "Биологические параметры видов", "yearly_conditions": "Условия по годам",
          "npc_stock": "Оценка запаса НПЦ", "npc_pdu": "ПДУ НПЦ"}

# Названия алгоритмов каталога — для сообщений о входах (решение № 70)
ALGO_TITLES = {"net_catchability": "a. Уловистость сети", "seine_catchability": "b. Уловистость невода",
               "seine_likelihood": "c. Правдоподобие методом площадей", "net_likelihood": "d. Правдоподобие балансовым методом",
               "seine_stock": "e. Запас методом площадей", "net_stock": "f. Запас балансовым методом",
               "combined_stock": "g. Запас, усреднённый по неводу и сети", "pdu_by_age": "h. ПДУ в экземплярах",
               "bayes_cohort": "i. Запас по математической модели", "forecast_pdu": "j. Прогноз и ПДУ по модели"}


class DataMissing(Exception):
    pass


def apply_fixed(params: dict) -> None:
    for k in FIXED_CONFIG:
        if k in params and params[k] is not None:
            cur = getattr(config, k)
            v = params[k]
            if isinstance(cur, str):
                v = str(v)
            elif isinstance(cur, bool) or cur is None:
                pass
            elif isinstance(cur, int):
                v = int(v)
            else:
                v = float(v)
            setattr(config, k, v)
    # число сетей одной ячеи по типу лова (научный, промысловый) — в манифесте двумя параметрами
    for k, types in (("NET_PANELS_SCIENTIFIC", ("научный", "scientific")), ("NET_PANELS_COMMERCIAL", ("промысловый", "commercial"))):
        if params.get(k) is not None:
            for t in types:
                config.NET_PANELS_BY_CATCH_TYPE[t] = int(params[k])


def bundle(ctx, *required: str) -> Bundle:
    missing = [c for c in required if c not in ctx.tables]
    if missing:
        from fishrunner import UserError
        raise UserError("Для водоёма не загружены наборы данных: " + ", ".join(TITLES.get(m, m) for m in missing))
    config.WATERBODY = ctx.water_body
    config.RESULTS_DIR = ctx.out_dir
    b = Bundle(ctx.water_body, ctx.tables, ctx.species_names, ctx.gear_kinds, ctx.dataset_sources)
    lo, hi = period(ctx)
    if lo is not None or hi is not None:
        b = keep_years(b, lambda y: (lo is None or y >= lo) and (hi is None or y <= hi))
    return b


# ---------------------------------------------------------------- период и входы расчёта (решение № 70)
def period(ctx) -> tuple[int | None, int | None]:
    """Период расчёта (годы с … по …); (None, None) — все годы данных."""
    p = (getattr(ctx, "raw", None) or {}).get("period") or {}
    lo, hi = p.get("from"), p.get("to")
    return (int(lo) if lo not in (None, "") else None), (int(hi) if hi not in (None, "") else None)


def keep_years(b: Bundle, keep) -> Bundle:
    """Тот же набор данных только за годы, для которых keep(год) истинно (строки без года — все)."""
    if not callable(keep):
        allowed = {int(y) for y in keep}
        keep = allowed.__contains__
    tables = {}
    for code, t in b.tables.items():
        rows = t.get("rows") or []
        if rows and any("year" in r for r in rows):
            t = {**t, "rows": [r for r in rows if r.get("year") is None or keep(int(r["year"]))]}
        tables[code] = t
    return Bundle(b.waterbody, tables, b.species_names, b.gear_kinds, b.sources)


def need_input(ctx, code: str) -> dict:
    """Состояние результата расчёта-входа алгоритма code (из расчёта, указанного во входах)."""
    from fishrunner import UserError
    if ctx.input_dir(code) is None:
        raise UserError(f"Не указан вход «{ALGO_TITLES.get(code, code)}»: выберите расчёт этого алгоритма "
                        "(по умолчанию — основной расчёт водоёма)")
    st = ctx.load_state(code)
    if st is None:
        raise UserError(f"У расчёта-входа «{ALGO_TITLES.get(code, code)}» нет результата — выполните его")
    return st


def years_for(ctx, data_years, **inputs) -> list[int]:
    """Годы расчёта: годы данных за период расчёта, которые есть у всех входов. Если входы рассчитаны за меньший
    период — расчёт выполняется за общие годы, об этом пишется замечание."""
    from fishrunner import UserError
    from .years import common_years, years_title
    data_years = [int(y) for y in data_years]
    out = common_years(data_years, *inputs.values())
    if not out:
        raise UserError("Нет общих лет у данных периода расчёта и расчётов-входов: "
                        + "; ".join(f"{ALGO_TITLES.get(k, k)} — {years_title(v)}" for k, v in inputs.items())
                        + f"; данные — {years_title(data_years)}")
    if out != data_years:
        short = [ALGO_TITLES.get(k, k) for k, v in inputs.items() if not set(data_years) <= set(int(y) for y in v)]
        ctx.note(f"Расчёт выполнен за {years_title(out)}: " + (
            "входы рассчитаны за меньший период — " + ", ".join(short) if short else "годы данных периода"))
    return out


def check_species(a: list, b: list, what: str) -> None:
    from fishrunner import UserError
    if list(a) != list(b):
        raise UserError(f"Виды {what} не совпадают с видами данных водоёма — пересчитайте вход по текущим данным")


def species_code(ctx, name_ru: str) -> str:
    for code, ru in ctx.species_names.items():
        if ru == name_ru:
            return code
    return name_ru


def in_period(ctx, years) -> list[int]:
    """Годы из списка, попадающие в период расчёта."""
    lo, hi = period(ctx)
    return [int(y) for y in years if (lo is None or int(y) >= lo) and (hi is None or int(y) <= hi)]
