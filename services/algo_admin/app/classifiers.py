"""
Справочники каталога алгоритмов (классификатор «Факторы» ТОФИ, файл заказчика 21.10.2026):
тип модели, метод расчёта запаса, значения параметров априорных распределений.
Казахские названия — перевод разработчика, на проверку.
"""
from __future__ import annotations

import re


def _rows(items):
    return [{"code": c, "name_ru": ru, "name_kk": kk, "tofi_code": t} for c, ru, kk, t in items]


MODEL_TYPES = _rows([
    ("deterministic", "детерминированный", "детерминирленген", "_FV_1115"),
    ("stochastic", "стохастический", "стохастикалық", "_FV_1119"),
])
STOCK_METHODS = _rows([
    ("area", "Метод площадей", "Аудан әдісі", "_FV_1129"),
    ("balance", "Балансовый метод", "Баланс әдісі", "_FV_1130"),
    ("model", "Математическая модель", "Математикалық модель", "_FV_1131"),
])
PARAM_VALUES = _rows([
    ("mu", "Математическое ожидание (μ)", "Математикалық күтім (μ)", "_FV_1124"),
    ("sigma", "Стандартное отклонение (σ)", "Стандартты ауытқу (σ)", "_FV_1125"),
    ("lower", "Нижняя граница", "Төменгі шек", "_FV_1126"),
    ("upper", "Верхняя граница", "Жоғарғы шек", "_FV_1127"),
])

ALL = {"model_types": MODEL_TYPES, "stock_methods": STOCK_METHODS, "param_values": PARAM_VALUES}

# классификация эталонных алгоритмов (по их описанию; меняет администратор в каталоге)
DEFAULT_CLASSIFICATION = {
    "seine_catchability": {"model_type": "deterministic", "stock_methods": ["area"]},
    "stock_by_catch": {"model_type": "deterministic", "stock_methods": ["area", "balance"]},
    "pdu_by_age": {"model_type": "deterministic", "stock_methods": []},
    "bayes_cohort": {"model_type": "stochastic", "stock_methods": ["model"]},
    "forecast_pdu": {"model_type": "stochastic", "stock_methods": ["model"]},
}

# какое значение распределения задаёт параметр профиля — по окончанию ключа
_KIND = [(re.compile(r"_mu$"), "mu"), (re.compile(r"_(sigma|sd)$"), "sigma"),
         (re.compile(r"_(lower|lo)$"), "lower"), (re.compile(r"_(upper|hi)$"), "upper")]


def value_kind(key: str) -> str | None:
    for rx, kind in _KIND:
        if rx.search(key or ""):
            return kind
    return None


def check(body: dict) -> list[str]:
    errs = []
    if body.get("model_type") not in (None, *[r["code"] for r in MODEL_TYPES]):
        errs.append(f"Неизвестный тип модели «{body.get('model_type')}»")
    bad = [m for m in body.get("stock_methods") or [] if m not in {r["code"] for r in STOCK_METHODS}]
    if bad:
        errs.append("Неизвестный метод расчёта запаса: " + ", ".join(bad))
    return errs
