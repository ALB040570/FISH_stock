# вариант объединения правдоподобии в один датафрейм
# и передачи заранее подготовленных параметров для каждого вида рыб

import os
import pymc as pm
import pytensor.tensor as pt
import numpy as np
import pandas as pd
import xarray as xr

from data_catch.zhaysan_fish_prop import m1_dict
from get_fish_prop import get_fish_prop
from get_stock_3d import get_stock_net_out_ages_3d, get_stock_net_with_ages_3d, get_stock_seine_out_ages_3d, get_stock_seine_with_ages_3d
from calc_pdu_in_pieces import calc_pdu_in_pieces
from get_yearly_stock_3d import (get_yearly_stock_net_out_ages_on_stock_3d, get_yearly_stock_net_with_ages_on_stock_3d,
                                 get_yearly_stock_seine_out_ages_on_stock_3d, get_yearly_stock_seine_with_ages_on_stock_3d)
# извлекаем чтобы сформировать начальный запас за нулевой год
from get_yearly_stock_3d import (get_yearly_stock_net_out_ages_on_catch_3d, get_yearly_stock_net_with_ages_on_catch_3d,
                                 get_yearly_stock_seine_out_ages_on_catch_3d, get_yearly_stock_seine_with_ages_on_catch_3d)


# подготовка данных для бацесовского вывода
# with_ages, если True - то на основе данных с учетом возрастов, если False - на основе данных без учета возрастов
def prepare_data_for_bayes(waterbody_name: str, fish_name: str, with_ages: bool):
    result = {}
    if with_ages:
        stock_by_date_net_3d = get_stock_net_with_ages_3d(waterbody_name)
        stock_by_date_seine_3d = get_stock_seine_with_ages_3d(waterbody_name)
        pdu_yearly_net_3d = calc_pdu_in_pieces(waterbody_name, 'сеть', True)
        pdu_yearly_seine_3d = calc_pdu_in_pieces(waterbody_name, 'невод', True)
        yearly_stock_net_3d = get_yearly_stock_net_with_ages_on_stock_3d('zhaysan')
        yearly_stock_seine_3d = get_yearly_stock_seine_with_ages_on_stock_3d('zhaysan')
        yearly_stock_net_on_catch_3d = get_yearly_stock_net_with_ages_on_catch_3d(waterbody_name)
        yearly_stock_seine_on_catch_3d = get_yearly_stock_seine_with_ages_on_catch_3d(waterbody_name)
    else:
        stock_by_date_net_3d = get_stock_net_out_ages_3d(waterbody_name)
        stock_by_date_seine_3d = get_stock_seine_out_ages_3d(waterbody_name)
        pdu_yearly_net_3d = calc_pdu_in_pieces(waterbody_name, 'сеть', False)
        pdu_yearly_seine_3d = calc_pdu_in_pieces(waterbody_name, 'невод', False)
        yearly_stock_net_3d = get_yearly_stock_net_out_ages_on_stock_3d('zhaysan')
        yearly_stock_seine_3d = get_yearly_stock_seine_out_ages_on_stock_3d('zhaysan')
        yearly_stock_net_on_catch_3d = get_yearly_stock_net_out_ages_on_catch_3d(waterbody_name)
        yearly_stock_seine_on_catch_3d = get_yearly_stock_seine_out_ages_on_catch_3d(waterbody_name)

    stock_by_date_net_3d = stock_by_date_net_3d.swap_dims({'LessAge': 'age'})
    stock_by_date_seine_3d = stock_by_date_seine_3d.swap_dims({'LessAge': 'age'})
    pdu_yearly_net_3d = pdu_yearly_net_3d.swap_dims({'LessAge': 'age'})
    pdu_yearly_seine_3d = pdu_yearly_seine_3d.swap_dims({'LessAge': 'age'})
    yearly_stock_net_3d = yearly_stock_net_3d.swap_dims({'LessAge': 'age'})
    yearly_stock_seine_3d = yearly_stock_seine_3d.swap_dims({'LessAge': 'age'})

    # Превращаем измерение age в целые числа
    pdu_yearly_net_3d = pdu_yearly_net_3d.assign_coords(age=pdu_yearly_net_3d.age.astype(int))
    pdu_yearly_seine_3d = pdu_yearly_seine_3d.assign_coords(age=pdu_yearly_seine_3d.age.astype(int))

    fishes_stock_by_date_net = stock_by_date_net_3d.FishType.values
    fishes_stock_by_date_seine = stock_by_date_seine_3d.FishType.values
    fishes_pdu_yearly_net = pdu_yearly_net_3d.FishType.values
    fishes_pdu_yearly_seine = pdu_yearly_seine_3d.FishType.values
    fishes_set = set(fishes_stock_by_date_net) & set(
        fishes_stock_by_date_seine) & set(fishes_pdu_yearly_net) & set(fishes_pdu_yearly_seine)
    fishes = list(fishes_set)

    # приводим количество рыб к одному множеству
    stock_by_date_net_3d = stock_by_date_net_3d.sel({'FishType': fishes})
    stock_by_date_seine_3d = stock_by_date_seine_3d.sel({'FishType': fishes})
    pdu_yearly_net_3d = pdu_yearly_net_3d.sel({'FishType': fishes})
    pdu_yearly_seine_3d = pdu_yearly_seine_3d.sel({'FishType': fishes})
    yearly_stock_net_3d = yearly_stock_net_3d.sel({'FishType': fishes})
    yearly_stock_seine_3d = yearly_stock_seine_3d.sel({'FishType': fishes})

    # 1. Заменяем NaN на нули
    pdu_yearly_net_3d = pdu_yearly_net_3d.fillna(0.0)
    pdu_yearly_seine_3d = pdu_yearly_seine_3d.fillna(0.0)
    yearly_stock_net_on_catch_3d = yearly_stock_net_on_catch_3d.fillna(0.0)
    yearly_stock_seine_on_catch_3d = yearly_stock_seine_on_catch_3d.fillna(0.0)

    pdu_combined_yearly = (pdu_yearly_net_3d + pdu_yearly_seine_3d) / 2
    yearly_stock_on_catch = (yearly_stock_net_on_catch_3d + yearly_stock_seine_on_catch_3d) / 2
    # извлекаем за 2015 год
    # Так как в 2015 году оценка по сетям = 0, берем только по неводу
    yearly_stock_0 = yearly_stock_seine_on_catch_3d.sel({'Year': 2015})

    stock_by_date_net_3d = stock_by_date_net_3d.assign_coords(Area=('Id', [0] * len(stock_by_date_net_3d['Id'])))

    # 1. Вычищаем скрытую подчиненную координату 'id' с маленькой буквы.
    # Главное измерение 'Id' (с большой буквы) останется абсолютно нетронутым!
    stock_net_safe = stock_by_date_net_3d.drop_vars('id', errors="ignore")
    stock_seine_safe = stock_by_date_seine_3d.drop_vars('id', errors="ignore")

    # Добавляем подчиненную координату Gear НЕ ИСПОЛЬЗУЕТСЯ!
    stock_by_date_net_3d = stock_net_safe.assign_coords(Gear=('Id', [0] * len(stock_by_date_net_3d['Id'])))
    stock_by_date_seine_3d = stock_seine_safe.assign_coords(Gear=('Id', [1] * len(stock_by_date_seine_3d['Id'])))

    stock_by_date_3d = xr.concat([stock_by_date_net_3d, stock_by_date_seine_3d], dim='Id')
    stock_by_date_3d['Id'] = np.arange(len(stock_by_date_3d['Id']))

    fish_props = get_fish_prop(waterbody_name)
    m0_dict = fish_props['возраст половой зрелости']
    result['m0'] = m0_dict[fish_name]

    m1_dict = fish_props['максимальный возраст']
    m1 = m1_dict[fish_name]
    result['m1'] = m1

    m2_dict = fish_props['возраст для хищников']
    result['m2'] = m2_dict[fish_name]

    fish_is_predator_dict = fish_props['признак хищника']
    result['is_predator'] = fish_is_predator_dict[fish_name]

    fecundity_bounds_dict = fish_props['количество икринок']
    result['fecundity_bounds_dict'] = fecundity_bounds_dict[fish_name]

    total_square_by_years = fish_props['площадь водоема']
    # Переводим словарь square_by_years в NumPy-вектор строго по порядку наших лет
    # Площадь в словаре должна быть в квадратных метрах!
    square_years_np = np.array([total_square_by_years[yr] * 1000000 for yr in total_square_by_years.keys()])
    result['square_years_np'] = square_years_np

    fish_density_dict = fish_props['максимальное количество мальков']
    # density_norms_np = np.array([fish_density_dict[f] for f in fishes])
    result['density_norms'] = fish_density_dict[fish_name]

    result['stock_by_date_fish'] = stock_by_date_3d.sel({'FishType': fish_name, 'age': slice(2, m1)})
    result['pdu_yearly_fish'] = pdu_combined_yearly.sel({'FishType': fish_name, 'age': slice(2, m1)})
    result['yearly_stock_net_fish'] = yearly_stock_net_3d.sel({'FishType': fish_name, 'age': slice(2, m1)})
    result['yearly_stock_seine_fish'] = yearly_stock_seine_3d.sel({'FishType': fish_name, 'age': slice(2, m1)})
    result['yearly_stock_0'] = yearly_stock_0.sel({'FishType': fish_name, 'age': slice(2, m1)})

    return result


def bayesian_assessment_twogear(waterbody_name: str, fish_name: str, with_ages: bool, draws = 2000, tune = 1500):
    prepared_data = prepare_data_for_bayes(waterbody_name, fish_name, with_ages)

    stock_by_date_fish = prepared_data['stock_by_date_fish']
    pdu_yearly_fish = prepared_data['pdu_yearly_fish']
    yearly_stock_net_fish = prepared_data['yearly_stock_net_fish']
    yearly_stock_seine_fish = prepared_data['yearly_stock_seine_fish']
    yearly_stock_0 = prepared_data['yearly_stock_0']
    m0 = prepared_data['m0']
    m1 = prepared_data['m1']
    m2 = prepared_data['m2']
    is_predator = prepared_data['is_predator']
    fecundity_bounds_tuple = prepared_data['fecundity_bounds_dict']
    square_years_np = prepared_data['square_years_np']
    density_norms = prepared_data['density_norms']

    # print('stock_by_date_fish = ', stock_by_date_fish)
    # print('pdu_yearly_fish = ', pdu_yearly_fish)
    # print('yearly_stock_net_fish = ', yearly_stock_net_fish)
    # print('yearly_stock_seine_fish = ', yearly_stock_seine_fish)
    # print('m0 = ', m0, type(m0))
    # print('m1 = ', m1, type(m1))
    # print('m2 = ', m2, type(m2))
    # print('fecundity_bounds_tuple = ', fecundity_bounds_tuple, type(fecundity_bounds_tuple))
    # print('square = ', square_years_np, type(square_years_np))
    # print('density_norms = ', density_norms, type(density_norms))
    # print('yearly_stock_0 = ', yearly_stock_0, yearly_stock_0.sum(dim="LessAge"))

    years = pdu_yearly_fish.Year.values

    # 1. АВТОМАТИЧЕСКОЕ РАСШИРЕНИЕ СЕТКИ ВОЗРАСТОВ (Добавляем less_1)
    orig_ages = np.arange(2, m1 + 1)
    ages = np.arange(1, m1 + 1)

    n_years, n_ages = len(years), len(ages)

    stock_by_date_clean_np = np.nan_to_num(stock_by_date_fish.values, nan=0.0) + 0.1
    pdu_yearly_clean_np = np.nan_to_num(pdu_yearly_fish, nan=0.0) + 0.1
    # Шаг 2: Суммируем запасы по имени измерения "age".
    # Метод .values превратит результат в чистую NumPy матрицу размера (10, 8) — Года х Виды
    yearly_stock_net_1d_clean = yearly_stock_net_fish.sum(dim=["age", 'Year']).values
    yearly_stock_seine_1d_clean = yearly_stock_seine_fish.sum(dim=["age", "Year"]).values

    # ВЫТАСКИВАЕМ ИНДИКАТОР ИЗ ПОДЧИНЕННОЙ КООРДИНАТЫ!
    # Превращаем текстовые "сеть"/"невод" в булевы/целочисленные 0 и 1 прямо на лету:
    # gear_indicator_np = stock_by_date_fish["Gear"].values

    # dates - перечень дат
    # y_to_idx - перечень номеров годов
    # id_y_idx - перечень годов по датам
    dates = pd.to_datetime(stock_by_date_fish.Date.values, dayfirst=True)
    y_to_idx = {yr: idx for idx, yr in enumerate(years)}
    id_y_idx = np.array([y_to_idx[d.year] for d in dates])

    # Генерация матрицы зрелости по формуле 1 / (1 + 4:(-(j-m0))
    # данная функция равна 0.2 в точке m0-1, равна 0.5 в точке m0 и равна 0.8 в точке m0+1
    eps_values = np.zeros(n_ages)
    for j, age in enumerate(ages):
        eps_values[j] = 1 / (1 + 4 ** (-(j + 1 - m0)))
    eps_const = eps_values

    # минимальное и максимальное количество икринок
    low_b = fecundity_bounds_tuple[0]
    high_b = fecundity_bounds_tuple[1]

    # ==============================================================================
    # РАСЧЕТ ГРАНИЦ ДЛЯ ОКН ПЛОДОВИТОСТИ (ВНЕ КОНТЕКСТА МОДЕЛИ)
    # ==============================================================================
    # Вычисляем размах видовой плодовитости для каждого вида рыб
    fec_range_np = high_b - low_b

    # Строго по вашей формуле фиксируем границы коридоров:
    fec_m0_lower_np = low_b
    fec_m0_upper_np = low_b + 0.1 * fec_range_np

    fec_m1_lower_np = high_b - 0.1 * fec_range_np
    fec_m1_upper_np = high_b

    # ==============================================================================
    # РАСЧЕТ МАТРИЦЫ ЕМКОСТИ СРЕДЫ
    # ==============================================================================
    # 1. Площадь нерестилищ по годам (10% от общей площади) -> Вектор-столбец (10, 1)
    S_ner_t = square_years_np * 0.10

    # 2. Нормативы плотности мальков по видам рыб -> Вектор-строка (1, 8)
    # norm_i = density_norms[np.newaxis, :]

    # 3. Динамический потолок емкости среды K (Матрица 10 x 8)
    K_dynamic = S_ner_t * density_norms * 10

    yearly_stock_0_np = yearly_stock_0.values

    # # Теперь обычные принты ПРЕКРАСНО сработают и покажут реальные числа:
    # print("--- Проверка географических масштабов водоема ---")
    # print("Площадь нерестилищ по годам (кв.м):\n", S_ner_t.round(0))
    # # print("Потолок мальков K (лещ в 2015):", int(K_dynamic[0, fishes.tolist().index("лещ")]))
    # # print("Потолок мальков K (судак в 2015):", int(K_dynamic[0, fishes.tolist().index("судак")]))
    # print(K_dynamic)
    # print("-------------------------------------------------")

    # измерение возрастов от 3 до m1
    age_truncated = orig_ages[1:]

    coords = {"Year": years, "age": ages, "Id": stock_by_date_fish.Id.values,
              "age_observed": orig_ages, "age_observed_truncated": age_truncated}

    print('Начинаем расчет по байесовской модели...')

    # ==============================================================================
    # НАЧАЛО БАЙЕСОВСКОГО ВЫВОДА ДЛЯ ДВУХ ОРУДИЙ ЛОВА (JOINT LIKELIHOOD)
    # ==============================================================================
    with pm.Model(coords=coords) as model:
        # m0 и m1 — это обычные числа Python, переданные в функцию (например, 4 и 11)
        m0_pt = pt.constant(m0, dtype="int64")
        m1_pt = pt.constant(m1, dtype="int64")
        m2_pt = pt.constant(m2, dtype="int64")
        # Объявляем density_alpha как матрицу. Теперь центр поиска mu меняется каждую секунду
        # в зависимости от того, какой сейчас год (площадь) и какой вид рыбы (норматив плотности)
        density_alpha = pm.LogNormal(
            "density_alpha",
            mu=0.0,
            sigma=0.2,
            dims=("Year",)
        )

        pdu_yearly_fish_pt = pm.Data(
            'pdu_yearly_fish_pt',
            pdu_yearly_clean_np,
        )

        # ==============================================================================
        # ИЗОЛИРОВАННЫЙ БИОЛОГИЧЕСКИЙ ПРИОР СМЕРТНОСТИ ДЛЯ ОДНОГО ВИДА РЫБЫ
        # ==============================================================================
        # Базовые скалярные priors для одной рыбы (dims больше не нужны)
        s_base = pm.LogNormal("s_base", mu=-3.2, sigma=0.2)

        # Два разных коэффициента крутизны для левого и правого крыла параболы
        # mu подбираем так, чтобы в точках 1 и m1 значение параболы было не меньше 1.
        s_juvenile_steep = pm.LogNormal("s_juvenile_steep", mu=-2.2, sigma=0.2)  # Спуск молоди
        s_aging_slow = pm.LogNormal("s_aging_slow", mu=-4.0, sigma=0.2)  # Подъем стариков

        # Строим плоскую годовую сетку возрастов. Размерность: (1 строка х m1 возрастов)
        # ages_grid_2d примет вид: [[1, 2, 3, ..., m1]]
        ages_grid_2d = pt.arange(1, n_ages + 1)[None, :]

        # Оптимальный возраст (возраст зрелости) для этой конкретной рыбы как скаляр
        # m0 — обычное число (например, 4.0 для судака или 3.0 для леща)
        optimal_age = m0_pt + 1.0

        # Расстояние до биологического оптимума. Размерность строго: (1, 16)
        age_distance = ages_grid_2d - optimal_age

        # Сборка крыльев параболы смертности — теперь это чистая 2D-математика (1, m1)
        s_curve_left = s_base + (age_distance ** 2) * s_juvenile_steep
        s_curve_right = s_base + (age_distance ** 2) * s_aging_slow

        # Гладкое склеивание ветвей параболы по условию оптимума. Размерность: (1, 16)
        s_curve_raw = pt.where(age_distance < 0, s_curve_left, s_curve_right)

        # --- ГОДОВЫЕ ФЛУКТУАЦИИ (Размерность сжимается до 1D вектора из 10 лет) ---
        # Убираем "FishType". Шум генерируется строго по годам хронологии (2015-2024)
        s_year_fluct_1d = pm.Normal("s_year_fluct", mu=0.0, sigma=0.05, dims=("Year",))

        # Разворачиваем флуктуацию лет (10,) в матрицу (10, 1) через dimshuffle
        # Дополнительная ось 'x' заставит PyTensor размножить этот годовой шум на все 16 возрастов!
        s_year_fluct_2d = s_year_fluct_1d.dimshuffle(0, 'x')

        # Применяем годовой шум к базовой параболе. Получаем матрицу размера (10 лет х 16 возрастов)
        s_raw_matrix = pt.exp(pt.log(s_curve_raw + 1e-6) + s_year_fluct_2d)

        # Маска живых возрастов. Сравниваем сетку (1, 16) со скаляром предельного возраста.
        # Результат: строка из 16 элементов, где после критического возраста стоят 0.0
        is_age_alive = pt.le(ages_grid_2d, m1_pt)

        # --- НОРМИРОВКА КРИВОЙ СМЕРТНОСТИ ---
        # Точка А: Значение левого крыла для СЕГОЛЕТОК (age = 1)
        distance_at_age_1 = 1.0 - optimal_age
        s_at_age_1 = s_base + (distance_at_age_1 ** 2) * s_juvenile_steep

        # Точка Б: Значение правого крыла для СТАРИКОВ (age = m1)
        distance_at_max_age = m1_pt - optimal_age
        s_at_max_age = s_base + (distance_at_max_age ** 2) * s_aging_slow

        # Истинный пик выгорания для данной рыбы (максимум между мальками и стариками)
        theoretical_peak = pt.maximum(s_at_age_1, s_at_max_age)
        s_peak_scale = pt.exp(pt.log(theoretical_peak + 1e-6))

        # Нормируем сырую годовую матрицу смертности
        s_normalized_raw = (s_raw_matrix / (s_peak_scale + 1e-6)) * 0.9

        # Накладываем маску живых возрастов и зажимаем смертность на безопасной полке 0.95
        # Итоговая матрица s_safe_matrix имеет строгую геометрию (10 лет х 16 возрастов)
        s_final_normalized = pt.where(is_age_alive, s_normalized_raw, 0.0)
        s_safe_matrix = pt.clip(s_final_normalized, 0.01, 0.9)

        # Регистрируем чистую 2D переменную смертности в модели
        s = pm.Deterministic("s", s_safe_matrix, dims=("Year", "age"))

        # ==============================================================================
        # ИНТЕНСИВНОСТЬ ВЫЕДАНИЯ ХИЩНИКАМИ ДЛЯ ОДНОГО ВИДА РЫБЫ (МАТРИЦА 2D)
        # ==============================================================================
        # Плоская сетка возрастов (1 строка х m1 возрастов): [[1, 2, 3, ..., m1]]
        ages_grid_2d = pt.arange(1, n_ages + 1)[None, :]

        # Маска кормового возраста: 1.0 для молоди, 0.0 для взрослых рыб (длина m1)
        h_mask_flat = pt.where(ages_grid_2d <= m2_pt, 1.0, 0.0)

        # Базовая годовая интенсивность выедания мальков (теперь это 1D вектор на 10 лет)
        # Убираем из dims координату "FishType"
        press_base = pm.LogNormal("press_base", mu=-1.3, sigma=0.13, dims=("Year",))

        # Пресс затухает по гиперболе (1 / age) и обнуляется маской для взрослых особей.
        # Разворачиваем press_base (10,) в (10, 1) через dimshuffle, чтобы PyTensor
        # автоматически растиражировал годовой пресс по всей оси возраста.
        # На выходе — честная 2D-матрица (10 лет х 16 возрастов)
        press_raw_matrix = pm.Deterministic(
            "press_raw",
            (press_base.dimshuffle(0, 'x') / pt.arange(1, n_ages + 1)[None, :]) * h_mask_flat,
            dims=("Year", "age")
        )

        # 1. Находим максимальный пресс внутри каждого года для этого вида рыбы.
        # Поскольку пресс затухает как 1/age, максимумом всегда будет пресс сеголеток (age 1).
        # keepdims=True сохраняет размерность матрицы (10, 1) для корректного деления шкал.
        press_max_per_year = pt.max(press_raw_matrix, axis=1, keepdims=True) + 1e-6

        # 2. Делим годовые ряды на их максимум (приводим шкалу строго к диапазону 0.0 - 1.0)
        # и умножаем на 0.3. Сеголетки (age 1) железно получат 0.3, а старшие возраста
        # плавно снизятся по гиперболе, полностью обнуляясь после порога m2.
        # 0.3 - максимальная доля жертвы от хищников для возрастов
        press_normalized = (press_raw_matrix / press_max_per_year) * 0.3

        # Записываем чистую, пропорционально сжатую годовую матрицу выедания в модель
        pred_press_cube = pm.Deterministic(
            "pred_press_cube",  # сохраняем старое имя переменной для совместимости с кодом ниже
            press_normalized,
            dims=("Year", "age")
        )

        # создаем измерение возрастов
        n_obs_ages = len(model.coords["age_observed"])
        obs_indices_pt = pt.constant(np.arange(1, n_obs_ages + 1), dtype="int64")
        #


        # ==============================================================================
        # 1. БРАКОНЬЕРСТВО ДЛЯ ОДНОГО ВИДА РЫБЫ (МАТРИЦА 2D: 10 лет х 16 возрастов)
        # ==============================================================================
        # Объявляем 1D-вектор коэффициентов по годам (длина 10 элементов)
        # lower=1.0 жестко страхует граф от отрицательных чисел и недолова ниже лимита.
        # mu=1.05 задает априорное ожидание: официальный вылов + 5% скрытого изъятия.
        beta_1d = pm.TruncatedNormal(
            "beta_1d",
            mu=1.0,
            sigma=0.06,
            lower=0.9,
            upper=1.3,
            dims=("Year",)
        )

        # РАЗВЕРТЫВАНИЕ В 2D МАТРИЦУ ЧЕРЕЗ DIMSHUFFLE И ALLOC
        # Добавляем фиктивную ось возраста: из вектора (10,) делаем матрицу (10, 1)
        beta_2d_single = beta_1d.dimshuffle(0, 'x')

        # Размножаем годовой коэффициент по оси возраста n_ages раз (n_ages = 16)
        # Это заполнит память и создаст честную матрицу формы (10 лет х 16 возрастов)
        beta_2d_full = pt.alloc(beta_2d_single, beta_1d.shape[0], n_ages)

        # Накладываем маску живых возрастов (is_age_alive имеет размерность (1, 16))
        # Для мертвых старших классов (например, 12–16 лет у судака) пресс принудительно зануляется.
        # Это защищает модель от генерации фантомной рыбы и выпрямляет Rhat < 1.01!
        beta_clean_matrix = pt.where(is_age_alive, beta_2d_full, 0.0)

        # Регистрируем в модели полноценную матрицу под старым именем для совместимости
        beta = pm.Deterministic("beta", beta_clean_matrix, dims=("Year", "age"))


        # ==============================================================================
        # УЛОВИСТОСТЬ СНАСТИ И ПОПОЛНЕНИЕ ДЛЯ ОДНОГО ВИДА РЫБЫ (МАТРИЦА 2D)
        # ==============================================================================

        q_raw = pm.Normal("q_raw", mu=0.0, sigma=0.5, dims=("age"))
        q_bias = pm.Deterministic("q_bias", pt.exp(q_raw), dims=("age"))

        # Выживаемость икры/молоди для ОДНОГО вида рыбы становится простым скаляром

        # Сэмплируем базовый коэффициент в человеческом масштабе (около 0.6)
        egg_survival_base = pm.Beta("egg_survival_base", alpha=4.0, beta=5.0)

        # Сдвигаем масштаб детерминистически в область долей процента
        egg_survival = pm.Deterministic("egg_survival", egg_survival_base * 0.1)



        # ==============================================================================
        # ИЗОЛИРОВАННАЯ ВОЗРАСТНАЯ ПЛОДОВИТОСТЬ ДЛЯ ОДНОГО ВИДА РЫБЫ (ВЕКТОР 1D: m1 классов)
        # ==============================================================================
        # fec_at_m0 — плодовитость самки в её самый первый нерест (скаляр, dims больше не нужны)
        # fec_at_m1 — максимальная плодовитость самки на закате жизни (скаляр)
        # Границы lower и upper — это обычные числа из вашей базы данных для текущего вида
        fec_at_m0 = pm.Uniform("fec_at_m0", lower=fec_m0_lower_np, upper=fec_m0_upper_np)
        fec_at_m1 = pm.Uniform("fec_at_m1", lower=fec_m1_lower_np, upper=fec_m1_upper_np)

        # Вычисляем шаг прироста количества икринок на 1 год жизни (чистый скаляр)
        # m1 и m0 — жесткие числовые константы возраста текущей рыбы (например, 11 и 4)
        fec_slope = (fec_at_m1 - fec_at_m0) / (m1_pt - m0_pt + 1e-6)

        # Строим плоский одномерный вектор возрастов модели. Длина ровно 16 элементов: [1, 2, 3, ..., 16]
        ages_vector = pt.arange(1, n_ages + 1)

        # ЛИНЕЙНОЕ УРАВНЕНИЕ ПЛОДОВИТОСТИ (Результат — вектор из 16 элементов)
        # Формула: Плод_текущая = Плод_при_созревании + Прирост * (Текущий_возраст - Возраст_созревания)
        theta_linear = fec_at_m0 + fec_slope * (ages_vector - m0_pt)

        # Биологическая маска безопасности: плодовитость не может быть отрицательной
        # на младших неполовозрелых возрастах (до наступления m0), поэтому все минусы принудительно зануляем.
        # Итоговая переменная theta_dyn — это честный 1D-вектор длиной 16 элементов
        theta_dyn = pm.Deterministic(
            "theta_dyn",
            pt.where(theta_linear > 0, theta_linear, 0.0),
            dims=("age",) # Координата FishType полностью ушла!
        )


        # Переводим среднее историческое значение в логарифмическую шкалу
        log_mu_older = np.log(yearly_stock_0_np)

        # Сэмплируем свободный логнормальный параметр
        X_initial_older_raw = pm.LogNormal("X_initial_older_raw", mu=log_mu_older, sigma=0.2, dims=("age_observed",))

        # Мягко, но надежно срезаем хвосты на уровне тензора, не ломая градиент распределения
        X_initial_older = pm.Deterministic(
            "X_initial_older",
            pt.clip(X_initial_older_raw, yearly_stock_0_np * 0.5, yearly_stock_0_np * 2.0),
            dims=("age_observed",)
        )


        # 2. РАСЧЕТ СЕГОЛЕТОК 2015 ГОДА ПО ВАШЕМУ АВТОРСКОМУ УРАВНЕНИЮ
        X_mature_2015 = X_initial_older * eps_const[1:]
        raw_egg_pool = theta_dyn[1:] * 0.5 * X_mature_2015
        total_eggs_laid = pt.sum(raw_egg_pool, axis=0)  # скаляр

        # egg_survival_print = pt_print.Print("ПЕЧАТАЕМ egg_survival = ")(egg_survival)
        # 2. Умножаем на базовую выживаемость икры (появление живых личинок)
        larvae_hatched = total_eggs_laid * egg_survival
        density_cap_2015 = pt.constant(K_dynamic[0]) * density_alpha[0]
        diff = density_cap_2015 - larvae_hatched
        smooth_max = pt.softplus(diff / 100000.0) * 100000.0
        effective_larvae = density_cap_2015 - smooth_max

        larvae_survived_year_2015 = effective_larvae * ((1.0 - s[0, 0]) ** 2)

        # 4. Финальная численность сеголеток 2015 года с учетом пресса хищников
        X_j1_2015 = larvae_survived_year_2015 / (1.0 + pred_press_cube[0, 0])

        # Склеиваем сеголеток и старшие группы в единую стартовую матрицу 2015 года (8 видов x 16 возрастов)
        X_initial_raw = pt.concatenate([X_j1_2015.dimshuffle('x'), X_initial_older], axis=0)

        # Обнуляем вымершие возраста уже в стартовом году
        ages_grid = pt.arange(1, n_ages + 1)
        # Вместо жесткого: pt.where(ages_grid <= m1_pt, X_initial_raw, 0.0)
        # Смягченное логистическое затухание:
        # Если возраст > m1_pt, коэффициент устремляется к 0 очень быстро, но плавно
        smooth_mask = 1.0 / (1.0 + pt.exp(5.0 * (ages_grid - m1_pt)))
        X_initial_clean = X_initial_raw * smooth_mask


        # Записываем в модель чистый стартовый куб
        X_initial = pm.Deterministic("X_initial", X_initial_clean, dims=("age",))

        X_list = [X_initial]

        # --- ЦИКЛ ПЕРЕХОДОВ (2016 - 2024) ---
        for t in range(1, n_years):
            X_prev = X_list[t - 1]
            s_t1 = s[t, :]
            pred_press_matrix_t = pred_press_cube[t, :]

            # ==================================================================
            # j=1 (СЕГОЛЕТКИ): ИСТОРИЧЕСКИ ПРАВИЛЬНЫЙ БИОЛОГИЧЕСКИЙ РАСЧЕТ
            # ==================================================================
            # 1. Сбор чистой отложенной икры от маточного стада прошлого года
            X_mature_prev = X_prev * eps_const
            raw_egg_pool = theta_dyn * X_mature_prev
            total_eggs_laid = pt.sum(raw_egg_pool, axis=0)  # скаляр

            # 2. Умножаем на базовую выживаемость икры (появление живых личинок)
            larvae_hatched = total_eggs_laid * egg_survival

            # Динамический потолок текущего года t без тяжелых экспонент
            density_cap_t = pt.constant(K_dynamic[t]) * density_alpha[t]

            diff = density_cap_t - larvae_hatched
            smooth_max = pt.softplus(diff / 100000.0) * 100000.0
            effective_larvae = density_cap_t - smooth_max

            # 4. Умножаем на КВАДРАТ выживаемости сеголеток (отход за год с весны по декабрь)
            # s_t1[:, 0] — это и есть годовая смертность сеголеток текущего года t
            larvae_survived_year = effective_larvae * ((1.0 - s_t1[0]) ** 2)  # Вектор (8,)

            # 5. Дополнительный экологический фильтр — выедание мальков хищниками водоема
            X_j1_new = larvae_survived_year / (1.0 + pred_press_matrix_t[0])

            # j=2 (двухлетки, индекс 1)
            numerator_j2 = (1.0 - s_t1[1]) * X_prev[0]
            X_j2_new = numerator_j2 / (1.0 + pred_press_matrix_t[1])

            # === СТАРШИЕ ВОЗРАСТА (Идеальная синхронизация 3D-параметров) ===
            # Вырезаем средние 14 классов (возраста 2..15) из 16-возрастных массивов модели
            X_prev_m1 = X_prev[1:-1]  # Размер (8, 14)
            s_prev_m1 = s_t1[1:-1]  # Размер (8, 14)

            # ИСПРАВЛЕНИЕ ДЛЯ BETA: берем те же средние 14 классов текущего года t
            beta_curr_older = beta[t, 1:-1]  # Теперь это строго (8, 14)!

            # ОДУ исходно содержит m1-1 элементов (возраста со 2 по m1).
            # Чтобы взять из него возраста со 2 по m1-1 (m1-2 классов), срез должен быть [:, :-1]
            A_curr_older = pdu_yearly_clean_np[t, :-1]

            num_older_raw = ((1.0 - s_prev_m1) * X_prev_m1) - (beta_curr_older * A_curr_older)
            # num_older = pt.softplus(num_older_raw)
            num_older = pt.maximum(num_older_raw, 1)

            # --- Знаменатель пресса хищников (возраста 3..m1, длина m1-2) ---
            older_grid = pt.arange(3, n_ages + 1)
            # m2_i = pt.constant(m2_prey_max_age_da.values[:, None])
            h_mask = pt.where(older_grid <= m2_pt, 1.0, 0.0)

            denominator_older = 1.0 + h_mask * pred_press_matrix_t[2:]

            X_older_new = num_older / denominator_older

            # ==============================================================================
            # ИДЕАЛЬНОЕ СВЯЗЫВАНИЕ ВОЗРАСТОВ В ОДИН ПЛОСКИЙ ВЕКТОР (16 классов)
            # ==============================================================================
            X_curr = pt.concatenate([[X_j1_new, X_j2_new], X_older_new], axis=0)

            X_curr = pt.softplus(X_curr)

            X_list.append(X_curr)

        X_estimated = pm.Deterministic("X_estimated", pt.stack(X_list, axis=0), dims=("Year", "age"))

        # ==============================================================================
        # ИЗОЛИРОВАННЫЙ БЛОК НАБЛЮДЕНИЙ ДЛЯ ОДНОГО ВИДА РЫБЫ (МАТРИЦЫ 2D)
        # ==============================================================================
        # Шаг 1: Извлекаем из матрицы X_estimated (10, 16) только наблюдаемые возраста (со 2 по 16 класс)
        # obs_indices_pt — ваш вектор индексов возрастов (длина 15 элементов)
        # На выходе получаем матрицу X_estimated_obs формы строго: (10 лет х 15 возрастов)
        X_estimated_obs = X_estimated.take(obs_indices_pt, axis=1)

        # Шаг 2: Извлекаем латентную численность под конкретный год каждой из 690 станций съемок
        # id_y_idx — ваш вектор индексов лет (длина 690 элементов)
        idx_joint_pt = pt.constant(id_y_idx, dtype="int64")

        # take(..., axis=0) размножит 10 лет хронологии вдоль всех 690 станций.
        # На выходе получаем матрицу X_at_date_joint формы строго: (690 станций х 15 возрастов)
        X_at_date_joint = X_estimated_obs.take(idx_joint_pt, axis=0)

        # Шаг 4: Синхронно отрезаем неловимых двухлеток, приводя оба тензора к форме (690, m1-2)
        # Из матрицы запаса (690, 15) убираем первый элемент (индекс 0) -> получаем (690, m1-2)
        X_at_date_joint_truncated = X_at_date_joint[:, 1:]

        # Из матрицы уловимости (690, m2) убираем первые два элемента (индексы 0 и 1) -> получаем (690, m1-2)
        q_bias_clean = q_bias[2:]

        # Шаг 5: Перемножаем две идеально выверенные матрицы (690, m1-2) на (690, m1-2)
        # Операция Elemwise пройдет без единого ворнинга, а координата FishType полностью стирается!
        expected_stock_joint = pm.Deterministic(
            "expected_stock_joint",
            X_at_date_joint_truncated * q_bias_clean,
            dims=("Id", "age_observed_truncated")
        )

        # ==============================================================================
        # РЕГИСТРАЦИЯ ОБЪЕДИНЕННОГО ПРАВДОПОДОБИЯ (+0.1 подложка)
        # ==============================================================================
        # mu_stock_joint_safe = pt.maximum(expected_stock_joint, 10)
        mu_stock_joint_safe = pm.math.softplus(expected_stock_joint - 10.0) + 10.0
        mu_stock_joint = pt.log(mu_stock_joint_safe)
        sigma_stock = pm.HalfNormal("sigma_stock", sigma=0.5)
        pm.LogNormal("obs_stock_joint",
                     mu=mu_stock_joint,
                     sigma=sigma_stock,
                     observed=stock_by_date_clean_np[..., 1:], # срез факта NumPy длины 14 классов
                     dims=("Id", "age_observed_truncated")) # Чистая 2D-сетка осей

        # Инициализация сбалансированной стартовой точки
        idata = pm.sample(
            draws=draws,
            tune=tune,
            random_seed=42,
            init="adapt_diag",
            target_accept=0.86,
            max_treedepth=12,
        )

        return idata


# Вычисляет и сохраняет результаты
def calc_stock_twogear(waterbody_name: str, fish_name: str, with_ages: bool, flag: str = ''):
    idata = bayesian_assessment_twogear(waterbody_name, fish_name, with_ages)

    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if not with_ages:
        output_nc_filename = f"{waterbody_name}_bayes_2g1p_out_ages_3d_{flag}.nc"
    else:
        output_nc_filename = f"{waterbody_name}_bayes_2g1p_with_ages_3d_{flag}.nc"

    output_nc_path = os.path.join(DATA_STOCK_DIR, output_nc_filename)

    print("\n--- Шаг 8: Сбор метрик, расчет био-баланса и экспорт в xr.Dataset ---")

    print("Доступные дочерние узлы:", list(idata.children.keys()))

    # 1. Явно переводим группу posterior из структуры DataTree в классический xarray.Dataset!
    posterior_ds = idata.posterior.to_dataset()

    # 2. Теперь методы схлопывания MCMC (.median и .quantile) отработают идеально!
    posterior_med = posterior_ds.median(dim=["chain", "draw"])
    posterior_q25 = posterior_ds.quantile(0.25, dim=["chain", "draw"])
    posterior_q75 = posterior_ds.quantile(0.75, dim=["chain", "draw"])

    # Извлекаем повозрастные кубы медиан для дальнейшего линейного перемножения
    X_med = posterior_med["X_estimated"]
    s_med = posterior_med["s"]
    beta_med = posterior_med["beta"]
    pred_press_med = posterior_med["pred_press_cube"]

    # Извлекаем цепочки для q_bias из idata
    q_bias_posterior = idata.posterior["q_bias"]
    # q_seine_posterior = idata.posterior["q_bias_seine"]

    # Расчет медиан (размерность FishType x age)
    q_med = q_bias_posterior.median(dim=("chain", "draw"))
    # q_seine_med = q_seine_posterior.median(dim=("chain", "draw"))

    pdu_yearly_fish_pt = idata["constant_data"]["pdu_yearly_fish_pt"].values

    # 4. РАСЧЕТ ЕЖЕГОДНОЙ ГИБЕЛИ РЫБ В ШТУКАХ (СТРОГО ПО ВАШЕЙ СТРУКТУРЕ ОДУ)
    dead_natural_pcs = s_med * X_med
    dead_predators_pcs = pred_press_med * X_med

    # Браконьерский перелов в штуках рыб: (beta - 1) * ОДУ
    dead_brac_pcs = (beta_med[:, 1:] - 1.0) * pdu_yearly_fish_pt
    dead_brac_pcs = xr.where(dead_brac_pcs < 0, 0.0, dead_brac_pcs)  # Защита от отрицательного прилова

    # Б. ИЗВЛЕЧЕНИЕ ТЕХНИЧЕСКИХ МЕТРИК КАЧЕСТВА (Rhat)
    # ----------------------------------------------------------------------
    # Рассчитываем матрицы Rhat для ключевых системных параметров
    rhat_dataset = xr.covariances = pm.stats.rhat(idata)
    rhat_X = rhat_dataset["X_estimated"]
    rhat_beta = rhat_dataset["beta"]
    # Расчет диагностики Rhat (сходимость по возрастам и видам)
    rhat_q_bias = rhat_dataset["q_bias"]
    # rhat_q_seine = rhat_dataset["q_bias_seine"]

    # Метод .drop_vars("quantile") стирает конфликтующий мета-тег,
    # полностью освобождая массивы для бесконфликтного слияния.
    X_q25_clean = posterior_q25["X_estimated"].drop_vars("quantile", errors="ignore")
    X_q75_clean = posterior_q75["X_estimated"].drop_vars("quantile", errors="ignore")

    beta_q25_clean = posterior_q25["beta"].drop_vars("quantile", errors="ignore")
    beta_q75_clean = posterior_q75["beta"].drop_vars("quantile", errors="ignore")

    # Расчет квантилей 25% и 75% для доверительных вееров в Streamlit
    q_bias_q25 = q_bias_posterior.quantile(0.25, dim=("chain", "draw")).drop_vars("quantile", errors="ignore")
    q_bias_q75 = q_bias_posterior.quantile(0.75, dim=("chain", "draw")).drop_vars("quantile", errors="ignore")

    # q_seine_q25 = q_seine_posterior.quantile(0.25, dim=("chain", "draw")).drop_vars("quantile", errors="ignore")
    # q_seine_q75 = q_seine_posterior.quantile(0.75, dim=("chain", "draw")).drop_vars("quantile", errors="ignore")

    # ----------------------------------------------------------------------
    # 6. СБОРКА ЕДИНОГО МОНОЛИТНОГО XR.DATASET И ЭКСПОРТ В NETCDF (.nc)
    # ----------------------------------------------------------------------
    ds_results = xr.Dataset(
        data_vars={
            # Медианы параметров
            "X_median": X_med,
            "s_median": s_med,
            "beta_median": beta_med,
            "pred_press_median": pred_press_med,
            "q_bias_median": q_med,

            # Квантили для затененных доверительных вееров в Streamlit
            "X_q25": X_q25_clean,
            "X_q75": X_q75_clean,
            "beta_q25": beta_q25_clean,
            "beta_q75": beta_q75_clean,
            "q_bias_q25": q_bias_q25,
            "q_bias_q75": q_bias_q75,

            # Физические объемы гибели и изъятия стада (в штуках)
            "dead_natural_pcs": dead_natural_pcs,
            "dead_predators_pcs": dead_predators_pcs,
            "dead_brac_pcs": dead_brac_pcs,
            "pdu_pcs": (["Year", "age_observed"], pdu_yearly_fish_pt),

            # Диагностика сходимости Гельмана-Рубина
            "rhat_X": rhat_X,
            "rhat_beta": rhat_beta,
            "rhat_q_bias": rhat_q_bias,
        },
        attrs={
            "waterbody": waterbody_name,
            "model_type": f"Two-Gear Bayesian Cohort Assessment fish = {fish_name}",
            "description": "Сбалансированные результаты оценки запасов рыб и браконьерства с объединенным правдоподобием",
            "total_divergences": int(idata.sample_stats["diverging"].sum().values)
        }
    )

    # ----------------------------------------------------------------------
    # Г. НАМЕРТВО СОХРАНЯЕМ DATASET В БИНАРНЫЙ ФАЙЛ NETCDF (.nc)
    # ----------------------------------------------------------------------

    ds_results.to_netcdf(output_nc_path, engine="netcdf4")

    print("🏁 Монолитный xr.Dataset успешно сохранен и готов к чтению в Streamlit!")


    return ds_results




if __name__ == '__main__':
    # result = calc_stock_twogear('zhaysan', False, 'test2_beta_4')
    result = calc_stock_twogear('zhaysan', 'карась', True, 'karas4')
    # karas1 - расчет после щуки
    # karas2 - target_accept=0.95 Финальный расчет.
    # karas3 - Финальный расчет.
    # karas4 - s_base_mu = -3.2. e0=0.1.
    # karas5 -

    print("\n" + "=" * 50)
    print("🐟 ДИНАМИКА ОБЩЕЙ ЧИСЛЕННОСТИ ПОПУЛЯЦИЙ ПО ГОДАМ (в штуках) 🐟")
    print("=" * 50)

    # 1. Извлекаем весь 3D-куб численности и берем медиану по всем сэмплам MCMC
    X_median = result["X_median"]

    # 2. Суммируем численность по оси возрастов (age), чтобы получить общий запас вида
    X_total_by_year = X_median.sum(dim="age")

    X_age2_10 = X_median.sel({'age': slice(2, 10)})
    X_total_age2_10 = X_age2_10.sum(dim='age')

    # 3. Переводим в удобную таблицу Pandas (строки — Года, колонки — Виды рыб)
    df_dynamics = X_median.to_pandas().T

    # Округляем до целых штук для биологической наглядности
    df_dynamics = df_dynamics.round(1)

    # Печатаем таблицу в консоль
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(df_dynamics)
    print("=" * 50)
    print("Суммарная численность по годам")
    print(X_total_by_year)
    print('Суммарная численность старше двух лет')
    print(X_total_age2_10.round(1))


    print("\n" + "=" * 50)
    print(f"📊 СТРУКТУРА СМЕРТНОСТИ  (в штуках по возрастам) 📊")
    print("=" * 50)

    # 1. Извлекаем весь 3D-куб численности и берем медиану по всем сэмплам MCMC
    s_median = result["s_median"]

    # Извлекаем срез по конкретному виду рыбы
    # Транспонируем (.T), чтобы Года стали колонками, а Возрасты — строками таблицы
    # df_cohorts = s_median.sel(FishType=target_fish).to_pandas().T

    # Печатаем когортную таблицу в консоль
    print(s_median.round(2))
    print("=" * 50)

    print("\n" + "=" * 50)
    print(f"📊 СТРУКТУРА БРАКЛНЬРСТВА  📊")
    print("=" * 50)

    # 1. Извлекаем весь 3D-куб численности и берем медиану по всем сэмплам MCMC
    beta_median = result["beta_median"]

    # Печатаем когортную таблицу в консоль
    print(beta_median.round(3))
    print("=" * 50)

    print("\n" + "=" * 50)
    print(f"📊 СТРУКТУРА УЛОВИСТОСТИ  📊")
    print("=" * 50)
    q_bias = result["q_bias_median"]

    # Извлекаем срез по конкретному виду рыбы
    # Транспонируем (.T), чтобы Года стали колонками, а Возрасты — строками таблицы
    df_cohorts = q_bias.to_pandas().T

    # Печатаем когортную таблицу в консоль
    print(df_cohorts)
    print("=" * 50)

    # ==============================================================================
    # КРАСИВЫЙ ВЫВОД НА ПЕЧАТЬ ИСХОДНЫХ ДАННЫХ ПДУ (В ШТУКАХ)
    # ==============================================================================
    # 1. Извлекаем массив ПДУ из узла констант по его текстовому имени
    pdu_matrix_np = result["pdu_pcs"].values

    # 2. Отрезаем подложку +0.1, если вы прибавляли её при подготовке данных
    pdu_matrix_np = pdu_matrix_np - 0.1

    # 3. Упаковываем в красивый DataFrame для вывода в консоль PyCharm
    # Вспоминаем: pdu содержит 15 возрастов (со 2 по 16 класс)
    age_pdu_columns = np.arange(1, m1_dict['карась'])
    years_list = np.arange(2015, 2025)

    df_pdu = pd.DataFrame(
        pdu_matrix_np,
        index=years_list,
        columns=age_pdu_columns
    ).T  # Транспонируем, чтобы года шли в столбцах, а возраста в строках

    print("\n" + "=" * 50)
    print("📊 СТРУКТУРА ОФИЦИАЛЬНОГО ПДУ ЛЕЩА (в штуках по возрастам) 📊")
    print("=" * 50)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(df_pdu.round(1))
    print("=" * 50 + "\n")

    print("\n" + "=" * 60)
    print("ФИНАЛЬНЫЙ АУДИТ БАЙЕСОВСКОЙ МОДЕЛИ (2 ПРАВДОПОДОБИЯ)")
    print("=" * 60)
    print(f"Общее число расходимостей (Divergences): {result.attrs['total_divergences']}")

    # Проверяем качество сходимости ключевых параметров
    max_rhat_X = float(result["rhat_X"].max())
    max_rhat_q_bias = float(result["rhat_q_bias"].max())
    # max_rhat_q_seine = float(result["rhat_q_bias_seine"].max())

    print(f"Максимальный Rhat для численности популяции X: {max_rhat_X:.3f}")
    print(f"Максимальный Rhat для смещения сетей (Ваша методка): {max_rhat_q_bias:.3f}")


    if max_rhat_X < 1.01 and result.attrs['total_divergences'] == 0:
        print("\n[УСПЕХ] Модель сошлась идеально. Геометрический конфликт полностью устранен!")
    else:
        print("\n[ВНИМАНИЕ] Имеются локальные проблемы со сходимостью. Проверьте веса Beta-распределений.")
    print("=" * 60 + "\n")
