"""
Настройки байесовской модели по видам: априорные распределения и варианты формул.

Значения по умолчанию точно повторяют последние версии скриптов старого проекта
(calc_stock_bayes_2g1p_*.py): lesh8, sudak4, okun5, plotva4, shuka6, sazan5, karas28, yaz5.
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

    # --- давление хищников: γ ~ 1/j до возраста m2 ---
    press_mu: float = -1.0
    press_sigma: float = 0.13
    press_max: float = 0.3

    # --- β: отклонение фактического вылова от ПДУ (браконьерство) ---
    beta_mu: float = 1.0
    beta_sigma: float = 0.06
    beta_lower: float = 0.9
    beta_upper: float = 1.4

    # --- поправка уловистости q по возрастам ---
    q_sigma: float = 0.5
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
    catch_mode: str = "tanh"         # "tanh" | "max" | "softplus"
    h_mask_mode: str = "sigmoid"     # "sigmoid" | "step"
    x_softplus: bool = True          # X = softplus(X) после шага
    pdu_scale: float = 1.0           # множитель ПДУ (km_pdu у карася)

    # --- правдоподобие ---
    unrecorded: str = "drop"         # ловы, где вид не учитывался: "drop" — исключить; "zero" — как в старом коде (0)
    likelihood_from: int = 3         # возраст j, с которого оценки по ловам входят в правдоподобие
    mu_floor: str = "softplus"       # "softplus" | "max" — нижняя граница ожидаемого запаса
    sigma_stock_sd: float = 0.5

    # --- выборка NUTS ---
    draws: int = 1000
    tune: int = 1000
    target_accept: float = 0.85
    max_treedepth: int = 12
    seed: int = 42
    chains: int = 0                  # 0 — как в PyMC по умолчанию

    # --- служебное: исходный скрипт (для режима сверки) ---
    script: str = ""
    old_flag: str = ""
    script_draws: int = 1000
    script_tune: int = 1000
    script_target_accept: float = 0.85


# Значения из последних версий скриптов старого проекта
DEFAULTS: dict[str, SpeciesConfig] = {
    "лещ": SpeciesConfig(
        s_base_mu=-1.9, s_base_sigma=0.2, s_juv_mu=-2.0, s_juv_sigma=0.2, s_age_mu=-4.6, s_age_sigma=0.2,
        s_norm=0.95, s_clip_lo=0.01, s_clip_hi=0.95, press_mu=-1.3, press_max=0.3,
        beta_sigma=0.06, beta_lower=0.9, beta_upper=1.3, egg_scale=0.003, theta_nonneg=True,
        x0_hi=2.0, catch_mode="max", h_mask_mode="step", x_softplus=False, mu_floor="softplus",
        script="calc_stock_bayes_2g1p_lesh", old_flag="lesh8", script_draws=2000, script_tune=1500),
    "судак": SpeciesConfig(
        s_base_mu=-2.2, s_base_sigma=0.1, s_juv_mu=-1.7, s_juv_sigma=0.1, s_age_mu=-4.6, s_age_sigma=0.2,
        s_norm=0.9, s_clip_lo=0.0, s_clip_hi=0.95, press_mu=-1.0, press_max=0.3,
        beta_lower=0.9, beta_upper=1.4, egg_scale=0.0006, theta_nonneg=False, unused_q_year_dev=True,
        x0_hi=1.3, catch_mode="max", h_mask_mode="step", x_softplus=True, mu_floor="max",
        script="calc_stock_bayes_2g1p_sudak", old_flag="sudak4", script_draws=1500, script_tune=2500),
    "окунь": SpeciesConfig(
        s_base_mu=-2.2, s_base_sigma=0.1, s_juv_mu=-1.2, s_juv_sigma=0.1, s_age_mu=-3.9, s_age_sigma=0.2,
        s_norm=0.95, s_clip_lo=0.0, s_clip_hi=0.95, press_mu=-1.0, press_max=0.3,
        beta_lower=0.9, beta_upper=1.4, egg_scale=0.005, theta_nonneg=True,
        x0_hi=1.3, catch_mode="tanh", h_mask_mode="sigmoid", x_softplus=True, mu_floor="softplus",
        script="calc_stock_bayes_2g1p_okun", old_flag="okun5", script_draws=2000, script_tune=1500),
    "плотва": SpeciesConfig(
        s_base_mu=-1.8, s_base_sigma=0.1, s_juv_mu=-1.7, s_juv_sigma=0.2, s_age_mu=-4.2, s_age_sigma=0.2,
        s_norm=0.95, s_clip_lo=0.0, s_clip_hi=0.95, press_mu=-1.0, press_max=0.3,
        beta_lower=0.9, beta_upper=1.4, egg_scale=0.003, theta_nonneg=True, density_softmin="plain",
        x0_hi=1.3, catch_mode="tanh", h_mask_mode="sigmoid", x_softplus=True, mu_floor="softplus",
        likelihood_from=2,
        script="calc_stock_bayes_2g1p_plotva", old_flag="plotva4", script_draws=1000, script_tune=1000),
    "щука": SpeciesConfig(
        s_base_mu=-2.7, s_base_sigma=0.1, s_juv_mu=-1.7, s_juv_sigma=0.1, s_age_mu=-3.2, s_age_sigma=0.2,
        s_norm=0.9, s_clip_lo=0.0, s_clip_hi=0.95, press_mu=-1.0, press_max=0.2,
        beta_lower=0.9, beta_upper=1.4, egg_scale=0.006, theta_nonneg=False, eggs_mode="older_half",
        fec_m1_width=0.05, x0_hi=1.3, catch_mode="tanh", h_mask_mode="sigmoid", x_softplus=True, mu_floor="max",
        script="calc_stock_bayes_2g1p_shuka", old_flag="shuka6", script_draws=1500, script_tune=2500),
    "сазан": SpeciesConfig(
        s_base_mu=-2.9, s_base_sigma=0.1, s_juv_mu=-2.2, s_juv_sigma=0.1, s_age_mu=-3.6, s_age_sigma=0.2,
        s_norm=0.9, s_clip_lo=0.0, s_clip_hi=0.95, press_mu=-1.0, press_max=0.3,
        beta_lower=0.9, beta_upper=1.4, egg_scale=0.003, theta_nonneg=True,
        x0_hi=1.3, catch_mode="tanh", h_mask_mode="sigmoid", x_softplus=True, mu_floor="softplus",
        script="calc_stock_bayes_2g1p_sazan", old_flag="sazan5", script_draws=1000, script_tune=1000),
    "карась": SpeciesConfig(
        s_base_mu=-3.2, s_base_sigma=0.2, s_juv_mu=-4.0, s_juv_sigma=0.2, s_age_mu=-5.3, s_age_sigma=0.2,
        s_norm=0.9, s_clip_lo=0.05, s_clip_hi=0.95, s_clip_mode="peak_switch", press_mu=-1.3, press_max=0.1,
        beta_sigma=0.6, beta_lower=0.9, beta_upper=13.3, egg_scale=0.001, theta_offset=1, theta_nonneg=True,
        x0_hi=2.0, catch_mode="softplus", h_mask_mode="step", x_softplus=True, mu_floor="softplus",
        script="calc_stock_bayes_2g1p_karas2", old_flag="karas28", script_draws=2000, script_tune=1500,
        script_target_accept=0.98),
    "язь": SpeciesConfig(
        s_base_mu=-2.2, s_base_sigma=0.1, s_juv_mu=-2.4, s_juv_sigma=0.1, s_age_mu=-4.9, s_age_sigma=0.2,
        s_norm=0.95, s_clip_lo=0.05, s_clip_hi=0.95, s_clip_mode="peak_switch", press_mu=-1.0, press_max=0.3,
        beta_lower=0.1, beta_upper=5.4, egg_scale=0.005, theta_nonneg=True,
        x0_hi=2.3, catch_mode="softplus", h_mask_mode="sigmoid", x_softplus=True, mu_floor="softplus",
        script="calc_stock_bayes_2g1p_yaz", old_flag="yaz5", script_draws=2000, script_tune=1500),
}

TOKENS = {"лещ": "lesh", "судак": "sudak", "окунь": "okun", "плотва": "plotva",
          "щука": "shuka", "сазан": "sazan", "карась": "karas", "язь": "yaz"}

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
    ("press_mu", "База давления: μ ln", "Хищники", "float", None),
    ("press_sigma", "База давления: σ", "Хищники", "float", None),
    ("press_max", "Максимальная доля гибели от хищников", "Хищники", "float", None),
    ("h_mask_mode", "Граница «корм хищников» в уравнении численности", "Хищники", "select",
     [("sigmoid", "плавная"), ("step", "ступенька")]),
    ("beta_mu", "β: μ", "Браконьерство β", "float", None),
    ("beta_sigma", "β: σ", "Браконьерство β", "float", None),
    ("beta_lower", "β: нижняя граница", "Браконьерство β", "float", None),
    ("beta_upper", "β: верхняя граница", "Браконьерство β", "float", None),
    ("catch_mode", "Вычитание вылова в уравнении численности", "Браконьерство β", "select",
     [("tanh", "плавное (tanh)"), ("max", "не меньше 1 рыбы (maximum)"), ("softplus", "доля вылова ≤ 0,95 (softplus)")]),
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
    ("unused_q_year_dev", "Лишний параметр q_year_dev (как у судака)", "Правдоподобие и формулы", "bool", None),
    ("draws", "Выборок на цепь", "Выборка NUTS", "int", None),
    ("tune", "Шагов настройки", "Выборка NUTS", "int", None),
    ("target_accept", "target_accept", "Выборка NUTS", "float", None),
    ("max_treedepth", "max_treedepth", "Выборка NUTS", "int", None),
    ("seed", "seed", "Выборка NUTS", "int", None),
    ("chains", "Цепей (0 — по умолчанию)", "Выборка NUTS", "int", None),
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
    if not (0 < cfg.x0_lo < cfg.x0_hi):
        errors.append("начальный запас: 0 < нижний множитель < верхнего")
    for k in ("s_base_sigma", "s_juv_sigma", "s_age_sigma", "s_year_sigma", "press_sigma", "beta_sigma",
              "q_sigma", "density_sigma", "x0_sigma", "sigma_stock_sd", "egg_alpha", "egg_beta", "egg_scale"):
        if getattr(cfg, k) <= 0:
            errors.append(f"{k} должно быть больше 0")
    if not (0 < cfg.target_accept < 1):
        errors.append("target_accept должен быть между 0 и 1")
    if cfg.draws < 10 or cfg.tune < 0:
        errors.append("слишком мало выборок")
    for k, *_rest in SCHEMA:
        opts = _rest[-1]
        if _rest[-2] == "select" and getattr(cfg, k) not in {v for v, _ in opts}:
            errors.append(f"{k}: недопустимое значение")
    if cfg.likelihood_from not in (2, 3):
        errors.append("правдоподобие может начинаться с j = 2 или j = 3")
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
