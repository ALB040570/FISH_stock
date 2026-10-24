"""
Настройки байесовской модели по видам: априорные распределения и варианты формул.

Значения по умолчанию повторяют последние версии скриптов старого проекта
(calc_stock_bayes_2g1p_*.py): lesh8, sudak4, okun5, plotva4, shuka6, sazan5, karas28, yaz5,
со следующими изменениями (ответ рецензентам, 18.10.2026):
    давление хищников без случайного параметра press_base: γ_j = γ_max · χ(j ≤ m2) / j (то же γ, что и раньше);
    изъятие в (17) у всех видов — плавное ограничение долей removal_cap выживших ("cap"; вариант
    старого скрипта — script_catch_mode, используется в режиме сверки);
    поправка уловистости сети q_net;
    дельта-логнормальное правдоподобие (likelihood = "delta"): ловы без рыбы вида — отдельная вероятность
    p0 = exp(−λ), λ = exp(c_орудия + b · ln(N/N̄)); ненулевые ловы — логнормальное без добавки obs_pad
    (у карася — гамма с постоянным коэффициентом вариации, delta_pos = "gamma");
    выборка: 4 цепи, target_accept 0,95 (у карася 0,98).
Изменения, сделанные на странице «Байесовская модель», сохраняются в
results/bayes_config.json (только отличия от значений скрипта).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

from .. import config as app_config


@dataclass
class SpeciesConfig:
    # --- естественная смертность: U-образная парабола с центром в m0 + 1 ---
    s_base_mu: float = -2.2
    s_base_sigma: float = 0.1
    s_juv_mu: float = -1.7          # крутизна для младших возрастов
    s_juv_sigma: float = 0.1
    s_age_mu: float = -4.6          # крутизна для старших возрастов
    s_age_sigma: float = 0.2
    s_year_sigma: float = 0.05      # годовые колебания
    s_norm: float = 0.9             # нормировка на теоретический максимум
    s_clip_lo: float = 0.0
    s_clip_hi: float = 0.95
    s_clip_mode: str = "normalized"  # "normalized" | "peak_switch" (карась, язь)

    # --- давление хищников: γ_j = γ_max · χ(j ≤ m2) / j (без случайных параметров) ---
    press_max: float = 0.3           # γ_max — доля гибели от хищников у сеголетков (j = 1)

    # --- β: отклонение фактического вылова от ПДУ (браконьерство) ---
    beta_mu: float = 1.0
    beta_sigma: float = 0.06
    beta_lower: float = 0.9
    beta_upper: float = 1.4

    # --- поправка уловистости q по возрастам ---
    q_sigma: float = 0.5
    gear_effect: bool = True         # поправка уловистости сети ln q_net ~ N(0, σ); невод — опорное орудие
    q_net_sigma: float = 1.0
    unused_q_year_dev: bool = False  # у судака параметр объявлен, но не используется

    # --- пополнение ---
    egg_alpha: float = 4.0
    egg_beta: float = 5.0
    egg_scale: float = 0.003         # выживаемость икры = Beta(α, β) × масштаб
    fec_m0_width: float = 0.1        # плодовитость в m0 ~ U[min, min + w·(max − min)]
    fec_m1_width: float = 0.1        # плодовитость в m1 ~ U[max − w·(max − min), max]
    theta_offset: int = 0            # θ(j) = θ(m0) + наклон·(j − m0 − offset); у карася offset = 1
    theta_nonneg: bool = True
    eggs_mode: str = "all_ages"      # "all_ages" | "older_half" (щука: возрасты 2+ и доля самок 0,5)
    density_sigma: float = 0.2       # множитель ёмкости по годам ~ LogNormal(0, σ)
    density_softmin: str = "scaled"  # "scaled" | "plain" (плотва)

    # --- начальный запас (первый год) ---
    x0_sigma: float = 0.2
    x0_lo: float = 0.5
    x0_hi: float = 1.3
    x0_source: str = "final"         # "final" — окончательный запас; "seine" — только невод

    # --- уравнение (17): вычитание вылова и маска хищников ---
    catch_mode: str = "cap"          # "cap" | "tanh" | "max" | "softplus"
    removal_cap: float = 0.95        # "cap": изъятие (вылов + браконьерство) не больше этой доли выживших
    removal_sharp: float = 50.0      # "cap": крутизна плавного ограничения (ошибка у границы ≤ ln 2 / крутизна)
    script_catch_mode: str = ""      # вариант (17) старого скрипта — для режима сверки
    h_mask_mode: str = "sigmoid"     # "sigmoid" | "step"
    x_softplus: bool = True          # X = softplus(X) после шага
    pdu_scale: float = 1.0           # множитель ПДУ (km_pdu у карася)

    # --- правдоподобие ---
    unrecorded: str = "drop"         # ловы, где вид не учитывался: "drop" — исключить; "zero" — как в старом коде (0)
    likelihood_from: int = 3         # возраст j, с которого оценки по ловам входят в правдоподобие
    mu_floor: str = "softplus"       # "softplus" | "max" — нижняя граница ожидаемого запаса
    sigma_stock_sd: float = 0.5
    obs_pad: float = 0.1             # добавка к оценкам запаса по ловам (только при likelihood = "pad")
    likelihood: str = "delta"        # "delta" — дельта-логнормальное; "pad" — логнормальное с добавкой obs_pad
    zero_c_sigma: float = 2.0        # c_орудия ~ N(0, zero_c_sigma): уровень ln λ при N = N̄
    zero_b_mu: float = 1.0           # b ~ N(zero_b_mu, zero_b_sigma): наклон ln λ по ln N (1 — пропорциональность)
    zero_b_sigma: float = 0.5
    delta_pos: str = "lognormal"     # ненулевые ловы при likelihood = "delta": "lognormal" — по возрастам;
                                     # "gamma" — гамма по возрастам, коэффициент вариации = sigma_stock;
                                     # "lognormal_total" — логнормальное для суммы по возрастам лова

    # --- выборка NUTS ---
    draws: int = 1000
    tune: int = 1000
    target_accept: float = 0.95
    max_treedepth: int = 12
    init: str = "adapt_diag"       # старт цепей NUTS: "adapt_diag" — все из одной точки; "jitter+adapt_diag" — с разбросом;
                                   # "multistart" — поиск максимума апостериорной плотности из init_starts точек, цепи стартуют из лучшей
    init_starts: int = 8
    seed: int = 42
    chains: int = 4                  # 0 — как в PyMC по умолчанию
    noncentered: bool = False        # нецентрированная запись s_year_fluct и beta_1d (при расходимостях)

    # --- служебное: исходный скрипт (для режима сверки) ---
    script: str = ""
    old_flag: str = ""
    script_draws: int = 1000
    script_tune: int = 1000
    script_target_accept: float = 0.95


# Значения из последних версий скриптов старого проекта
DEFAULTS: dict[str, SpeciesConfig] = {
    "лещ": SpeciesConfig(
        s_base_mu=-1.9, s_base_sigma=0.2, s_juv_mu=-2.0, s_juv_sigma=0.2, s_age_mu=-4.6, s_age_sigma=0.2,
        s_norm=0.95, s_clip_lo=0.01, s_clip_hi=0.95, press_max=0.3,
        beta_sigma=0.06, beta_lower=0.9, beta_upper=1.3, egg_scale=0.003, theta_nonneg=True,
        x0_hi=2.0, script_catch_mode="max", h_mask_mode="step", x_softplus=False, mu_floor="softplus",
        script="calc_stock_bayes_2g1p_lesh", old_flag="lesh8", script_draws=2000, script_tune=1500),
    "судак": SpeciesConfig(
        s_base_mu=-2.2, s_base_sigma=0.1, s_juv_mu=-1.7, s_juv_sigma=0.1, s_age_mu=-4.6, s_age_sigma=0.2,
        s_norm=0.9, s_clip_lo=0.0, s_clip_hi=0.95, press_max=0.3,
        beta_lower=0.9, beta_upper=1.4, egg_scale=0.0006, theta_nonneg=False, unused_q_year_dev=False,  # было True (лишний параметр скрипта судака), отключено 18.10.2026
        x0_hi=1.3, script_catch_mode="max", h_mask_mode="step", x_softplus=True, mu_floor="max",
        script="calc_stock_bayes_2g1p_sudak", old_flag="sudak4", script_draws=1500, script_tune=2500),
    "окунь": SpeciesConfig(
        s_base_mu=-2.2, s_base_sigma=0.1, s_juv_mu=-1.2, s_juv_sigma=0.1, s_age_mu=-3.9, s_age_sigma=0.2,
        s_norm=0.95, s_clip_lo=0.0, s_clip_hi=0.95, press_max=0.3,
        beta_sigma=0.2, beta_lower=0.7, beta_upper=1.4,  # окунь: недолов до 0,7 ПДУ (решение автора 18.10.2026)
        init="multistart",  # две моды: из одной точки цепи застревают в худшей (падение запаса)
        egg_scale=0.005, theta_nonneg=True,
        x0_hi=1.3, script_catch_mode="tanh", h_mask_mode="sigmoid", x_softplus=True, mu_floor="softplus",
        script="calc_stock_bayes_2g1p_okun", old_flag="okun5", script_draws=2000, script_tune=1500),
    "плотва": SpeciesConfig(
        s_base_mu=-1.8, s_base_sigma=0.1, s_juv_mu=-1.7, s_juv_sigma=0.2, s_age_mu=-4.2, s_age_sigma=0.2,
        s_norm=0.95, s_clip_lo=0.0, s_clip_hi=0.95, press_max=0.3,
        beta_lower=0.9, beta_upper=1.4, egg_scale=0.003, theta_nonneg=True, density_softmin="plain",
        x0_hi=1.3, script_catch_mode="tanh", h_mask_mode="sigmoid", x_softplus=True, mu_floor="softplus",
        likelihood_from=2, likelihood="pad",  # плотва: с дельта-логнормальным правдоподобием нет сходимости; прежний вариант (решение автора 19.10.2026)
        script="calc_stock_bayes_2g1p_plotva", old_flag="plotva4", script_draws=1000, script_tune=1000),
    "щука": SpeciesConfig(
        s_base_mu=-2.7, s_base_sigma=0.1, s_juv_mu=-1.7, s_juv_sigma=0.1, s_age_mu=-3.2, s_age_sigma=0.2,
        s_norm=0.9, s_clip_lo=0.0, s_clip_hi=0.95, press_max=0.2,
        beta_lower=0.9, beta_upper=1.4, egg_scale=0.006, theta_nonneg=False, eggs_mode="older_half",
        likelihood_from=4,  # трёхлетки щуки облавливаются плохо (когорты 3→4 ×18,6), решение 18.10.2026
        fec_m1_width=0.05, x0_hi=1.3, script_catch_mode="tanh", h_mask_mode="sigmoid", x_softplus=True, mu_floor="max",
        script="calc_stock_bayes_2g1p_shuka", old_flag="shuka6", script_draws=1500, script_tune=2500),
    "сазан": SpeciesConfig(
        s_base_mu=-2.9, s_base_sigma=0.1, s_juv_mu=-2.2, s_juv_sigma=0.1, s_age_mu=-3.6, s_age_sigma=0.2,
        s_norm=0.9, s_clip_lo=0.0, s_clip_hi=0.95, press_max=0.3,
        beta_lower=0.9, beta_upper=1.4, egg_scale=0.003, theta_nonneg=True,
        x0_hi=1.3, script_catch_mode="tanh", h_mask_mode="sigmoid", x_softplus=True, mu_floor="softplus",
        script="calc_stock_bayes_2g1p_sazan", old_flag="sazan5", script_draws=1000, script_tune=1000),
    "карась": SpeciesConfig(
        s_base_mu=-3.2, s_base_sigma=0.2, s_juv_mu=-4.0, s_juv_sigma=0.2, s_age_mu=-5.3, s_age_sigma=0.2,
        s_norm=0.9, s_clip_lo=0.05, s_clip_hi=0.95, s_clip_mode="peak_switch", press_max=0.3,  # было 0.1 (флаг karas28), 0.3 по решению автора 20.10.2026
        beta_lower=0.9, beta_upper=1.4,  # было σ 0.6, верх 13.3 (ошибка), исправлено 18.10.2026
        egg_scale=0.001, theta_offset=1, theta_nonneg=True,
        x0_hi=2.0, script_catch_mode="softplus", h_mask_mode="step", x_softplus=True, mu_floor="softplus",
        script="calc_stock_bayes_2g1p_karas2", old_flag="karas28", script_draws=2000, script_tune=1500,
        target_accept=0.98, script_target_accept=0.98,
        delta_pos="gamma", sigma_stock_sd=3.0),  # карась: с логнормальным для ненулевых ловов нет сходимости; гамма (решение автора 19.10.2026)
    "язь": SpeciesConfig(
        s_base_mu=-2.2, s_base_sigma=0.1, s_juv_mu=-2.4, s_juv_sigma=0.1, s_age_mu=-4.9, s_age_sigma=0.2,
        s_norm=0.95, s_clip_lo=0.05, s_clip_hi=0.95, s_clip_mode="peak_switch", press_max=0.3,
        beta_lower=0.9, beta_upper=1.4,  # было 0.1–5.4 (ошибка), исправлено 18.10.2026
        egg_scale=0.005, theta_nonneg=True,
        x0_hi=2.3, script_catch_mode="softplus", h_mask_mode="sigmoid", x_softplus=True, mu_floor="softplus",
        script="calc_stock_bayes_2g1p_yaz", old_flag="yaz5", script_draws=2000, script_tune=1500),
}

# Режим legacy: модель старой программы на входных данных forecast (решение автора 19.10.2026).
# Карась — src/calc_stock_bayes_2g1p_karas.py старого проекта (последний запуск karas5): логнормальное
# правдоподобие с добавкой 0,1, без поправки уловистости сети и без отдельной вероятности пустых ловов,
# вылов в (17) — maximum(…, 1), γ_max 0,3, выживаемость икры Beta(4, 5) × 0,1, β ∈ [0,9; 1,3], NUTS 1000/1500, 0,86.
LEGACY: dict[str, dict] = {
    "карась": dict(
        s_base_mu=-3.2, s_base_sigma=0.2, s_juv_mu=-2.2, s_juv_sigma=0.2, s_age_mu=-4.0, s_age_sigma=0.2,
        s_year_sigma=0.05, s_norm=0.9, s_clip_lo=0.01, s_clip_hi=0.9, s_clip_mode="normalized", press_max=0.3,
        beta_mu=1.0, beta_sigma=0.06, beta_lower=0.9, beta_upper=1.3, q_sigma=0.5, gear_effect=False,
        egg_alpha=4.0, egg_beta=5.0, egg_scale=0.1, fec_m0_width=0.1, fec_m1_width=0.1, theta_offset=0,
        theta_nonneg=True, eggs_mode="all_ages", density_sigma=0.2, density_softmin="scaled",
        x0_sigma=0.2, x0_lo=0.5, x0_hi=2.0, x0_source="seine",
        catch_mode="max", h_mask_mode="step", x_softplus=True, pdu_scale=1.0,
        unrecorded="zero", likelihood_from=3, mu_floor="softplus", sigma_stock_sd=0.5,
        likelihood="pad", obs_pad=0.1,
        draws=1000, tune=1500, target_accept=0.86, max_treedepth=12, init="adapt_diag", seed=42, chains=4,
        noncentered=False),
}

TOKENS = {"лещ": "lesh", "судак": "sudak", "окунь": "okun", "плотва": "plotva",
          "щука": "shuka", "сазан": "sazan", "карась": "karas", "язь": "yaz"}

# FishStock: коды видов других водоёмов (жерех, сом, …) — из справочника «Виды рыб» (register_tokens)
_EXTRA_TOKENS: dict[str, str] = {}


def register_tokens(names: dict[str, str]) -> None:
    """{название вида: код справочника} — для видов, которых нет в TOKENS (имена файлов и каталогов результатов)."""
    for ru, code in (names or {}).items():
        if ru not in TOKENS and code:
            _EXTRA_TOKENS[ru] = str(code)


def token(species: str) -> str:
    """Код вида для имён файлов: TOKENS, затем коды справочника, иначе само название."""
    return TOKENS.get(species) or _EXTRA_TOKENS.get(species) or species


# Описание полей для формы на странице: (ключ, подпись, группа, тип, варианты/подсказка)
SCHEMA = [
    ("s_base_mu", "База смертности: μ ln", "Естественная смертность", "float", None),
    ("s_base_sigma", "База смертности: σ", "Естественная смертность", "float", None),
    ("s_juv_mu", "Крутизна для молоди: μ ln", "Естественная смертность", "float", None),
    ("s_juv_sigma", "Крутизна для молоди: σ", "Естественная смертность", "float", None),
    ("s_age_mu", "Крутизна для старших: μ ln", "Естественная смертность", "float", None),
    ("s_age_sigma", "Крутизна для старших: σ", "Естественная смертность", "float", None),
    ("s_year_sigma", "Годовые колебания: σ", "Естественная смертность", "float", None),
    ("s_norm", "Нормировка на максимум", "Естественная смертность", "float", None),
    ("s_clip_lo", "Нижняя граница s", "Естественная смертность", "float", None),
    ("s_clip_hi", "Верхняя граница s", "Естественная смертность", "float", None),
    ("s_clip_mode", "Обрезка s", "Естественная смертность", "select",
     [("normalized", "по нормированной кривой"), ("peak_switch", "с переключением по максимуму (карась, язь)")]),
    ("press_max", "γ_max: доля гибели от хищников у сеголетков (γ_j = γ_max / j до m2)", "Хищники", "float", None),
    ("h_mask_mode", "Граница «корм хищников» в уравнении численности", "Хищники", "select",
     [("sigmoid", "плавная"), ("step", "ступенька")]),
    ("beta_mu", "β: μ", "Браконьерство β", "float", None),
    ("beta_sigma", "β: σ", "Браконьерство β", "float", None),
    ("beta_lower", "β: нижняя граница", "Браконьерство β", "float", None),
    ("beta_upper", "β: верхняя граница", "Браконьерство β", "float", None),
    ("catch_mode", "Вычитание вылова в уравнении численности", "Браконьерство β", "select",
     [("cap", "плавное ограничение изъятия долей выживших (все виды)"), ("tanh", "плавное (tanh)"),
      ("max", "не меньше 1 рыбы (maximum)"), ("softplus", "доля вылова ≤ 0,95 (softplus)")]),
    ("removal_cap", "Изъятие не больше доли выживших", "Браконьерство β", "float", None),
    ("removal_sharp", "Крутизна ограничения изъятия", "Браконьерство β", "float", None),
    ("pdu_scale", "Множитель ПДУ", "Браконьерство β", "float", None),
    ("egg_scale", "Выживаемость икры: масштаб", "Пополнение", "float", None),
    ("egg_alpha", "Выживаемость икры: Beta α", "Пополнение", "float", None),
    ("egg_beta", "Выживаемость икры: Beta β", "Пополнение", "float", None),
    ("fec_m0_width", "Плодовитость в m0: ширина интервала", "Пополнение", "float", None),
    ("fec_m1_width", "Плодовитость в m1: ширина интервала", "Пополнение", "float", None),
    ("theta_offset", "Сдвиг плодовитости (j − m0 − сдвиг)", "Пополнение", "int", None),
    ("theta_nonneg", "Плодовитость не меньше 0", "Пополнение", "bool", None),
    ("eggs_mode", "Кто нерестится", "Пополнение", "select",
     [("all_ages", "все возрасты, без доли самок"), ("older_half", "возрасты 1–2 и старше, доля самок 0,5 (щука)")]),
    ("density_sigma", "Ёмкость по годам: σ", "Пополнение", "float", None),
    ("density_softmin", "Ограничение мальков ёмкостью", "Пополнение", "select",
     [("scaled", "масштаб 100 000"), ("plain", "без масштаба (плотва)")]),
    ("x0_sigma", "Начальный запас: σ", "Начальный запас", "float", None),
    ("x0_lo", "Начальный запас: не меньше × оценки", "Начальный запас", "float", None),
    ("x0_hi", "Начальный запас: не больше × оценки", "Начальный запас", "float", None),
    ("x0_source", "Начальный запас по данным", "Начальный запас", "select",
     [("final", "окончательный запас (сеть и невод)"), ("seine", "только невод")]),
    ("x_softplus", "Сглаживание численности (softplus)", "Правдоподобие и формулы", "bool", None),
    ("unrecorded", "Ловы, где вид не учитывался", "Правдоподобие и формулы", "select",
     [("drop", "исключить (как на этапе 2)"), ("zero", "считать нулевым уловом")]),
    ("likelihood_from", "Правдоподобие с возраста j", "Правдоподобие и формулы", "int", None),
    ("mu_floor", "Нижняя граница ожидаемого запаса", "Правдоподобие и формулы", "select",
     [("softplus", "плавная (softplus, 10)"), ("max", "жёсткая (maximum, 10)")]),
    ("sigma_stock_sd", "Шум наблюдений: σ HalfNormal", "Правдоподобие и формулы", "float", None),
    ("q_sigma", "Поправка уловистости q: σ", "Правдоподобие и формулы", "float", None),
    ("gear_effect", "Поправка уловистости сети q_net", "Правдоподобие и формулы", "bool", None),
    ("q_net_sigma", "ln q_net: σ", "Правдоподобие и формулы", "float", None),
    ("likelihood", "Правдоподобие оценок по ловам", "Правдоподобие и формулы", "select",
     [("delta", "дельта-логнормальное (пустые ловы отдельно)"), ("pad", "логнормальное с добавкой obs_pad")]),
    ("obs_pad", "Добавка к оценкам по ловам", "Правдоподобие и формулы", "float", None),
    ("zero_c_sigma", "Пустые ловы: σ уровня c", "Правдоподобие и формулы", "float", None),
    ("zero_b_mu", "Пустые ловы: μ наклона b", "Правдоподобие и формулы", "float", None),
    ("zero_b_sigma", "Пустые ловы: σ наклона b", "Правдоподобие и формулы", "float", None),
    ("delta_pos", "Ненулевые ловы (дельта)", "Правдоподобие и формулы", "select",
     [("lognormal", "логнормальное по возрастам"), ("gamma", "гамма по возрастам"),
      ("lognormal_total", "логнормальное для суммы по возрастам")]),
    ("unused_q_year_dev", "Лишний параметр q_year_dev (как у судака)", "Правдоподобие и формулы", "bool", None),
    ("draws", "Выборок на цепь", "Выборка NUTS", "int", None),
    ("tune", "Шагов настройки", "Выборка NUTS", "int", None),
    ("target_accept", "target_accept", "Выборка NUTS", "float", None),
    ("max_treedepth", "max_treedepth", "Выборка NUTS", "int", None),
    ("init", "Старт цепей", "Выборка NUTS", "select",
     [("adapt_diag", "все из одной точки"), ("jitter+adapt_diag", "с разбросом"),
      ("multistart", "из лучшего из нескольких максимумов")]),
    ("init_starts", "Старт цепей: число точек поиска", "Выборка NUTS", "int", None),
    ("seed", "seed", "Выборка NUTS", "int", None),
    ("chains", "Цепей (0 — по умолчанию)", "Выборка NUTS", "int", None),
    ("noncentered", "Нецентрированные годовые эффекты (s, β)", "Выборка NUTS", "bool", None),
]
EDITABLE = {k for k, *_ in SCHEMA}


def config_path() -> Path:
    return app_config.RESULTS_DIR / "bayes_config.json"


def _load_overrides() -> dict:
    p = config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _coerce(key: str, value):
    ftype = {f.name: f.type for f in fields(SpeciesConfig)}[key]
    if ftype in ("float", float):
        return float(value)
    if ftype in ("int", int):
        return int(value)
    if ftype in ("bool", bool):
        return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "да", "on")
    return str(value)


# FishStock: настройки задаются не файлом, а профилем водоёма и параметрами запуска (см. set_runtime)
_RUNTIME: dict | None = None


def set_runtime(overrides: dict | None) -> None:
    """{вид: {параметр: значение}} — профиль водоёма + параметры запуска. None — как в исходном проекте."""
    global _RUNTIME
    _RUNTIME = overrides


def base_config(species: str) -> SpeciesConfig:
    """Значения по умолчанию: скрипты оз. Жайсан для известных видов, иначе — общие значения SpeciesConfig."""
    return DEFAULTS.get(species, SpeciesConfig())


def get_config(species: str) -> SpeciesConfig:
    """Настройки вида: значения скрипта + сохранённые изменения."""
    if _RUNTIME is not None:
        over = _RUNTIME.get(species, {})
        clean = {k: _coerce(k, v) for k, v in over.items() if k in EDITABLE}
        return replace(base_config(species), **clean)
    base = DEFAULTS[species]
    over = _load_overrides().get(species, {})
    clean = {k: _coerce(k, v) for k, v in over.items() if k in EDITABLE}
    return replace(base, **clean)


def overrides(species: str) -> dict:
    return {k: v for k, v in _load_overrides().get(species, {}).items() if k in EDITABLE}


def validate(species: str, values: dict) -> list[str]:
    cfg = replace(base_config(species), **{k: _coerce(k, v) for k, v in values.items() if k in EDITABLE})
    errors = []
    if not (0 <= cfg.s_clip_lo < cfg.s_clip_hi <= 1):
        errors.append("границы s должны быть 0 ≤ нижняя < верхняя ≤ 1")
    if not (cfg.beta_lower < cfg.beta_upper):
        errors.append("β: нижняя граница должна быть меньше верхней")
    if cfg.init_starts < 1:
        errors.append("старт цепей: число точек поиска должно быть не меньше 1")
    if not (0 < cfg.x0_lo < cfg.x0_hi):
        errors.append("начальный запас: 0 < нижний множитель < верхнего")
    for k in ("s_base_sigma", "s_juv_sigma", "s_age_sigma", "s_year_sigma", "beta_sigma", "q_sigma", "q_net_sigma",
              "density_sigma", "x0_sigma", "sigma_stock_sd", "egg_alpha", "egg_beta", "egg_scale", "obs_pad",
              "removal_sharp", "zero_c_sigma", "zero_b_sigma"):
        if getattr(cfg, k) <= 0:
            errors.append(f"{k} должно быть больше 0")
    if not (0 < cfg.removal_cap < 1):
        errors.append("доля изъятия должна быть между 0 и 1")
    if cfg.press_max < 0:
        errors.append("γ_max не может быть отрицательным")
    if not (0 < cfg.target_accept < 1):
        errors.append("target_accept должен быть между 0 и 1")
    if cfg.draws < 10 or cfg.tune < 0:
        errors.append("слишком мало выборок")
    for k, *_rest in SCHEMA:
        opts = _rest[-1]
        if _rest[-2] == "select" and getattr(cfg, k) not in {v for v, _ in opts}:
            errors.append(f"{k}: недопустимое значение")
    if not 2 <= cfg.likelihood_from <= 6:
        errors.append("правдоподобие может начинаться с возраста j от 2 до 6")
    return errors


def save_overrides(species: str, values: dict) -> SpeciesConfig:
    """Сохранить значения формы: в файл пишутся только отличия от скрипта."""
    errors = validate(species, values)
    if errors:
        raise ValueError("; ".join(errors))
    base = asdict(DEFAULTS[species])
    diff = {}
    for k, v in values.items():
        if k in EDITABLE:
            cv = _coerce(k, v)
            if cv != base[k]:
                diff[k] = cv
    data = _load_overrides()
    if diff:
        data[species] = diff
    else:
        data.pop(species, None)
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return get_config(species)


def reset(species: str) -> SpeciesConfig:
    data = _load_overrides()
    data.pop(species, None)
    p = config_path()
    if p.exists():
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return DEFAULTS[species]


def schema_payload() -> list[dict]:
    return [{"key": k, "label": lab, "group": g, "type": t,
             "options": [{"value": v, "label": l} for v, l in opts] if opts else None}
            for k, lab, g, t, opts in SCHEMA]
