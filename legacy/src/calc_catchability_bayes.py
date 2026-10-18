import numpy as np
import xarray as xr
import pymc as pm
import pytensor.tensor as pt
import os

from get_catch_3d import get_catch_net_3d, get_catch_seine_3d
from get_fish_prop import get_fish_prop


def process_seine_bayes(
    da_year_fish, age_numeric_values, max_allowed_age, base_fish_eff
):
    """Рассчитывает уловистость невода по трехмерному срезу xarray

    [Id x FishType x LessAge] за один конкретный год для одного вида рыбы.
    """

    # 1. АЛГОРИТМ РАСЧЕТА t50 ПО КУМУЛЯТИВНОЙ СУММЕ ГОДА
    # Схлопываем измерение Id (даты), собирая общую сумму уловов по возрастам за весь год
    yearly_catch_by_age = da_year_fish.sum(dim="Id").values
    total_yearly_catch = np.sum(yearly_catch_by_age)

    # Защита от нулевого годового улова
    if total_yearly_catch == 0:
        return np.zeros(len(age_numeric_values))

    # Находим медианный возраст по накопленной сумме года
    cumulative_catch = np.cumsum(yearly_catch_by_age)
    median_idx = np.where(cumulative_catch >= total_yearly_catch / 2)[0][0]
    calculated_t50_prior = float(age_numeric_values[median_idx])

    # 2. ПОДГОТОВКА TOTAL_OBSERVED (вектор общих уловов по датам/Id)
    # Схлопываем измерение LessAge (возрасты), оставляя динамику уловов по дням
    total_observed = da_year_fish.sum(dim="LessAge").values

    # Если вектор дат пуст или содержит только нули, сэмплинг не требуется
    if np.sum(total_observed) == 0:
        return np.zeros(len(age_numeric_values))

    # 3. БАЙЕСОВСКАЯ S-МОДЕЛЬ (PyMC)
    with pm.Model() as model:
        # t50 центрируется вокруг эмпирически рассчитанного медианного возраста
        t50 = pm.Normal("t50", mu=calculated_t50_prior, sigma=1.5)
        alpha = pm.HalfNormal("alpha", sigma=1.0)

        # Логистическое плато селективности активного орудия
        logistic_profile = 1.0 / (
            1.0 + pt.exp(-alpha * (age_numeric_values - t50))
        )

        # Маскируем возраста, превышающие жизненный цикл вида
        masked_seine_profile = pt.switch(
            age_numeric_values > max_allowed_age, 0.0, logistic_profile
        )

        # Нормируем профиль (взрослое плато = 1.0)
        seine_age_efficiency = masked_seine_profile / pt.max(
            masked_seine_profile
        )
        pm.Deterministic("age_profile", seine_age_efficiency)

        # Расчет общего коэффициента уловистости этого года
        prior_mu = base_fish_eff * pt.mean(seine_age_efficiency)
        corrected_efficiency = pm.TruncatedNormal(
            "corrected_efficiency",
            mu=prior_mu,
            sigma=0.15,
            lower=0.01,
            upper=1.0,
        )

        # Функция правдоподобия оценивает ожидаемый улов за каждую отдельную дату (Id)
        expected_catch = corrected_efficiency * total_observed
        catch_noise = np.std(total_observed) + 1.0

        likelihood = pm.Normal(
            "likelihood",
            mu=expected_catch,
            sigma=catch_noise,
            observed=total_observed,
        )

        # Запуск сэмплинга MCMC
        idata = pm.sample(
            draws=1000,
            tune=1000,
            target_accept=0.95,
            return_inferencedata=True,
            progressbar=False,
        )

    # 4. ПОСТ-ОБРАБОТКА И КЛИППИРОВАНИЕ
    post_efficiency_mean = float(idata.posterior["corrected_efficiency"].mean())
    post_age_profile_mean = (
        idata.posterior["age_profile"].mean(dim=["chain", "draw"]).values
    )

    # Перемножаем общий коэффициент на форму распределения по возрастам
    final_age_efficiencies = post_efficiency_mean * post_age_profile_mean

    # Корректируем минимальный положительный шум порогом 0.1
    low_positive_mask = (final_age_efficiencies > 0) & (
        final_age_efficiencies <= 0.1
    )
    final_age_efficiencies[low_positive_mask] = 0.1

    return final_age_efficiencies

def calc_catchability_net_3d_old(waterbody_name: str):
    """
    Основная функция расчета скорректированных коэффициентов уловистости.
    Возвращает заполненный трехмерный xr.DataArray (Year, FishType, LessAge).
    """
    # получаем трехмерный массив об уловах
    catch_3d = get_catch_net_3d(waterbody_name)

    fish_props = get_fish_prop(waterbody_name)
    k_catchability_dict = fish_props['коэффициент уловистости']
    max_ages_dict = fish_props['максимальный возраст']
    m0_dict = fish_props['возраст половой зрелости']

    print("--- Шаг 1: Агрегация xarray и поиск пиковых возрастов ---")

    years_list = sorted(list(set(catch_3d.Year.values)))
    # Находим пересечение видов рыб с помощью оператора &
    common_fish = set(k_catchability_dict.keys()) & set(max_ages_dict.keys()) & set(catch_3d.coords['FishType'].values)

    # Превращаем результат обратно в список (если нужно для циклов или срезов xarray)
    fish_types = list(common_fish)

    catch_3d_filtered = catch_3d.sel(FishType=fish_types)

    age_numeric_values = catch_3d_filtered.coords["age"].values
    annual_catch_by_fish_age = catch_3d_filtered.groupby("Year").sum(dim="Id")

    peak_age_indices = {}
    for year in years_list:
        peak_age_indices[year] = {}
        for fish in fish_types:
            fish_yearly_data = annual_catch_by_fish_age.sel(Year=year, FishType=fish)
            max_idx = int(fish_yearly_data.argmax(dim="LessAge"))
            # пиковый возраст не может быть меньше возраста половой зрелости
            peak_age_indices[year][fish] = max(max_idx, m0_dict[fish])

    print("\n--- Шаг 2: Запуск байесовского вывода в PyMC --- орудие лова = сеть")

    # Создаем пустой NumPy массив нужной формы для сбора результатов: (Года, Виды рыб, Возраста)
    # Форма: (len(years), len(fish_types), len(ages))
    result_matrix = np.zeros((len(years_list), len(fish_types), len(catch_3d_filtered.LessAge.values)))

    for y_idx, year in enumerate(years_list):
        for f_idx, fish in enumerate(fish_types):
            peak_idx = peak_age_indices[year][fish]
            peak_age_val = age_numeric_values[peak_idx]

            observed_vector = annual_catch_by_fish_age.sel(Year=year, FishType=fish).values
            total_observed = np.sum(observed_vector)

            base_fish_eff = k_catchability_dict[fish]
            max_allowed_age = max_ages_dict[fish]

            with pm.Model() as model:
                # Настройка параметров логнормального распределения по возрастам
                sigma_log = 0.25
                mu_log = np.log(peak_age_val) + (sigma_log ** 2)

                # lognorm_dist = pm.LogNormal.dist(mu=mu_log, sigma=sigma_log)
                # pdf_values = pt.exp(pm.logp(lognorm_dist, age_numeric_values))

                # заменяем предыдущие де строки на следующие 7 строк
                # 2. Описываем два линейных участка (Y = Y1 + k * (X - X1))
                # Участок 1: растет от 1.0 до val_peak
                k1 = (peak_age_val - 0.1) / (peak_idx - 1)
                line_up = 0.1 + k1 * (age_numeric_values - 1)

                # Участок 2: убывает от val_peak до 0.1
                k2 = (0.1 - peak_age_val) / (max_allowed_age - peak_idx)
                line_down = peak_age_val + k2 * (age_numeric_values - peak_idx)

                # 3. Объединяем участки через условия (если возраст < пика, то line_up, иначе line_down)
                pdf_values = pt.switch(age_numeric_values < peak_idx, line_up, line_down)

                # 4. Ограничиваем края (за пределами [age_start, age_max] плотность равна 0)
                pdf_values = pt.switch(age_numeric_values < 1, 0.0, pdf_values)
                pdf_values = pt.switch(age_numeric_values > max_allowed_age, 0.0, pdf_values)

                # Маскируем возраста, превышающие максимальный жизненный цикл вида
                masked_pdf = pt.switch(age_numeric_values > max_allowed_age, 0.0, pdf_values)

                # Нормируем профиль (в пике экспертная уловистость = 1.0)
                expert_age_efficiency = masked_pdf / pt.max(masked_pdf)
                mean_expert_age_eff = pt.mean(expert_age_efficiency)

                # Мы регистрируем этот профиль как детерминированную переменную,
                # чтобы PyMC посчитал его числовые значения и вернул нам наружу
                pm.Deterministic("age_profile", expert_age_efficiency)

                # Формируем априорное математическое ожидание
                prior_mu = base_fish_eff * mean_expert_age_eff

                # Скорректированный общий коэффициент уловистости
                corrected_efficiency = pm.TruncatedNormal(
                    "corrected_efficiency",
                    mu=prior_mu, sigma=0.15, lower=0.1, upper=1.0
                )

                # Функция правдоподобия (Likelihood)
                expected_catch = corrected_efficiency * total_observed
                catch_noise = np.std(observed_vector) + 1.0

                likelihood = pm.Normal(
                    "likelihood",
                    mu=expected_catch, sigma=catch_noise, observed=total_observed
                )

                # Повышаем target_accept до 0.95 и увеличиваем фазу адаптации (tune) до 1000
                idata = pm.sample(
                    draws=1000,
                    tune=1000,
                    target_accept=0.95,
                    return_inferencedata=True,
                    progressbar=False
                )

            # Извлекаем апостериорные средние значения
            post_efficiency_mean = float(idata.posterior["corrected_efficiency"].mean())
            post_age_profile_mean = idata.posterior["age_profile"].mean(dim=["chain", "draw"]).values

            # Рассчитываем финальный коэффициент для каждого возраста:
            # Общий скорректированный коэффициент умножаем на форму распределения по возрастам
            final_age_efficiencies = post_efficiency_mean * post_age_profile_mean

            # Создаем маску: ищем элементы, которые строго больше 0, но меньше или равны 0.1
            low_positive_mask = (final_age_efficiencies > 0) & (
                    final_age_efficiencies <= 0.1
            )

            # Принудительно подтягиваем эти значения к порогу 0.01 (нули при этом не изменятся!)
            final_age_efficiencies[low_positive_mask] = 0.1
            # ---------------------------------------------------------

            # Записываем вектор (размером 15) в нашу итоговую матрицу результатов
            result_matrix[y_idx, f_idx, :] = final_age_efficiencies
            print(f"Расчет завершен для: Год {year} | Вид: {fish} орудие лова = сеть")

    # --- Шаг 3: Сборка итогового трехмерного xr.DataArray ---
    output_da = xr.DataArray(
        data=result_matrix,
        coords={
            "Year": years_list,
            "FishType": fish_types,
            "LessAge": catch_3d_filtered.LessAge.values
        },
        dims=["Year", "FishType", "LessAge"],
        name="corrected_catchability_coefficient"
    )

    # Дополнительно переносим подчиненную числовую координату Age для удобства
    output_da = output_da.assign_coords(age=("LessAge", age_numeric_values))

    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    # сохраняем коэффициенты уловистости по возрастам для сети
    output_nc_filename_net = f"{waterbody_name}_catchability_net_3d.nc"
    output_nc_path_net = os.path.join(DATA_STOCK_DIR, output_nc_filename_net)
    output_da.to_netcdf(output_nc_path_net, engine="netcdf4")

    return output_da

def calc_catchability_seine_3d(waterbody_name):
    catch_3d = get_catch_seine_3d(waterbody_name)
    fish_props = get_fish_prop(waterbody_name)
    k_catchability_dict = fish_props['коэффициент уловистости невода']
    max_ages_dict = fish_props['максимальный возраст']

    years_list = sorted(list(set(catch_3d.Year.values)))

    # Находим пересечение видов рыб с помощью оператора &
    common_fish = set(k_catchability_dict.keys()) & set(max_ages_dict.keys()) & set(catch_3d.coords['FishType'].values)

    # Превращаем результат обратно в список (если нужно для циклов или срезов xarray)
    fish_types = list(common_fish)

    catch_3d_filtered = catch_3d.sel(FishType=fish_types)

    age_numeric_values = catch_3d_filtered.coords["age"].values
    annual_catch_by_fish_age = catch_3d_filtered.groupby("Year").sum(dim="Id")

    # Создаем пустой NumPy массив нужной формы для сбора результатов: (Года, Виды рыб, Возраста)
    # Форма: (len(years), len(fish_types), len(ages))
    result_matrix = np.zeros((len(years_list), len(fish_types), len(catch_3d_filtered.LessAge.values)))

    for y_idx, year in enumerate(years_list):
        for f_idx, fish in enumerate(fish_types):
            catch_3d_filtered_year_fish = catch_3d_filtered.sel(Year=year, FishType=fish)
            final_age_efficiencies = process_seine_bayes(catch_3d_filtered_year_fish, age_numeric_values, max_ages_dict[fish], k_catchability_dict[fish])
            # Записываем вектор (размером 15) в нашу итоговую матрицу результатов
            result_matrix[y_idx, f_idx, :] = final_age_efficiencies
            print(f"Расчет завершен для: Год {year} | Вид: {fish} орудие лова = невод")

    # --- Сборка итогового трехмерного xr.DataArray ---
    output_da = xr.DataArray(
        data=result_matrix,
        coords={
            "Year": years_list,
            "FishType": fish_types,
            "LessAge": catch_3d_filtered.LessAge.values
        },
        dims=["Year", "FishType", "LessAge"],
        name="corrected_catchability_coefficient_seine"
    )

    # Дополнительно переносим подчиненную числовую координату Age для удобства
    output_da = output_da.assign_coords(age=("LessAge", age_numeric_values))

    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    # сохраняем коэффициенты уловистости по возрастам для невода
    output_nc_filename_seine = f"{waterbody_name}_catchability_seine_3d.nc"
    output_nc_path_seine = os.path.join(DATA_STOCK_DIR, output_nc_filename_seine)
    output_da.to_netcdf(output_nc_path_seine, engine="netcdf4")

    return output_da

def calc_catchability_net_3d(waterbody_name: str):
    # Намертво фиксируем красивый десятичный вывод в консоли без экспонент 'e-04'
    np.set_printoptions(suppress=True, precision=2)
    """
    Сверхбыстрый расчет 3D-куба технологической уловистости (от 0.10 до 0.85)
    на базе асимметричных логистических кривых с пологим правым склоном.
    Размерность куба: 10 лет х 8 видов х 15 возрастов (от 2 до 16 лет).
    """
    # ----------------------------------------------------------------------
    # ШАГ 1: ЗАГРУЗКА ИСХОДНЫХ ДАННЫХ И БИОЛОГИЧЕСКИХ ПАРАМЕТРОВ
    # ----------------------------------------------------------------------
    catch_3d = get_catch_net_3d(waterbody_name)
    fish_props = get_fish_prop(waterbody_name)

    k_catchability_dict = fish_props['коэффициент уловистости сети']
    max_ages_dict = fish_props['максимальный возраст']
    m0_dict = fish_props['возраст половой зрелости']

    print("\n--- Шаг 1: Агрегация xarray и поиск биологических пиков ---")

    years_list = sorted(list(set(catch_3d.Year.values)))
    common_fish = set(k_catchability_dict.keys()) & set(max_ages_dict.keys()) & set(
        catch_3d.coords['FishType'].values)
    fish_types = sorted(list(common_fish))

    catch_3d_filtered = catch_3d.sel(FishType=fish_types)

    # Массив реальных биологических возрастов (например, [2, 3, 4 ... 16], длина 15)
    age_numeric_values = catch_3d_filtered.coords["age"].values
    n_ages = len(age_numeric_values)

    # Стартовый возраст съемок (обычно равен 2)
    age_start = age_numeric_values[0]

    annual_catch_by_fish_age = catch_3d_filtered.groupby("Year").sum(dim="Id")

    # Поиск биологических пиков улова (смещенных к m0 при необходимости)
    peak_age_values_dict = {}
    for year in years_list:
        peak_age_values_dict[year] = {}
        for fish in fish_types:
            fish_yearly_data = annual_catch_by_fish_age.sel(Year=year, FishType=fish)
            raw_max_idx = int(fish_yearly_data.argmax(dim="LessAge"))
            real_peak_age = age_numeric_values[raw_max_idx]

            final_biological_peak_age = max(real_peak_age, m0_dict[fish])
            peak_age_values_dict[year][fish] = final_biological_peak_age

    print("\n--- Шаг 2: Скоростное аналитическое конструирование асимметричных кривых ---")

    # Создаем итоговый пустой NumPy-массив нужного размера: (10 лет х 8 видов х 15 возрастов)
    result_matrix = np.zeros((len(years_list), len(fish_types), n_ages))

    # Логарифмическая константа падения хвостов ровно до уровня 0.10
    # Находится из уравнения логистики: 1 / (1 + exp(target)) = 0.10 => target = ln(1/0.10 - 1) = ln(9)
    log_target_floor = np.log(1.0 / 0.10 - 1.0)  # Примерно 2.197

    # Двойной цикл по годам хронологии и видам рыб
    for y_idx, year in enumerate(years_list):
        for f_idx, fish in enumerate(fish_types):
            peak_age_val = peak_age_values_dict[year][fish]
            max_allowed_age = max_ages_dict[fish]
            base_fish_eff = k_catchability_dict[fish]  # Экспертная норма среднего (например, 0.40)

            # ----------------------------------------------------------------------
            # А. МАТЕМАТИЧЕСКИЙ РАСЧЕТ АСИММЕТРИЧНЫХ СКЛОНОВ КРИВОЙ
            # ----------------------------------------------------------------------
            # Защита от деления на ноль, если пик улова совпал с краями жизненного цикла
            dist_left = max(float(peak_age_val - age_start), 0.5)
            dist_right = max(float(max_allowed_age - peak_age_val), 0.5)

            # Вычисляем индивидуальную крутизну для левой и правой части
            # Правая крутизна k_down автоматически получится более пологой, так как dist_right > dist_left!
            k_up = log_target_floor / dist_left
            k_down = log_target_floor / dist_right

            # Собираем гладкие логистические склоны
            sel_up = 1.0 / (1.0 + np.exp(-k_up * (age_numeric_values - peak_age_val)))
            sel_down = 1.0 / (1.0 + np.exp(k_down * (age_numeric_values - peak_age_val)))

            # Математическое слияние в идеальный асимметричный колокол с пиком ровно 1.0!
            # Левый хвост в возрасте 2 года и правый хвост в возрасте max_allowed_age теперь ГАРАНТИРОВАННО равны 0.10!
            abstract_bell_np = sel_up * sel_down

            # Жестко обнуляем глубоких стариков за пределами жизненного цикла вида
            older_than_max_mask = age_numeric_values > max_allowed_age
            abstract_bell_np[older_than_max_mask] = 0.0

            # ----------------------------------------------------------------------
            # Б. ИНТЕЛЛЕКТУАЛЬНАЯ МИНИМАКС-НОРМИРОВКА К КОРРИДОРУ `[0.1, 0.85]`
            # ----------------------------------------------------------------------
            # Находим количество живых возрастов
            active_age_mask = age_numeric_values <= max_allowed_age
            n_active_ages = np.sum(active_age_mask)

            # Вычисляем среднее арифметическое и максимум нашей новой пологой кривой
            current_biological_mean = np.sum(abstract_bell_np[active_age_mask]) / n_active_ages
            current_max = np.max(abstract_bell_np)

            # Рассчитываем конкурирующие коэффициенты масштабирования
            coeff_mean = float(base_fish_eff) / (current_biological_mean + 1e-12)
            coeff_max = 0.85 / (current_max + 1e-12)

            # ВАШЕ МИНИМАКСНОЕ РЕШЕНИЕ: Выбираем самый безопасный множитель
            final_scale_factor = min(coeff_mean, coeff_max)

            # Пропорционально масштабируем весь вектор
            final_age_efficiencies = abstract_bell_np * final_scale_factor

            # ----------------------------------------------------------------------
            # В. ФИНАЛЬНЫЙ ЗАМОК: ГАРАНТИРУЕМ ПОДЛУЖКУ 0.10 ДЛЯ ЖИВЫХ ВОЗРАСТОВ
            # ----------------------------------------------------------------------
            low_value_mask = (final_age_efficiencies < 0.1) & active_age_mask
            final_age_efficiencies[low_value_mask] = 0.1
            final_age_efficiencies[older_than_max_mask] = 0.0

            # Записываем результат в итоговый 3D-куб
            result_matrix[y_idx, f_idx, :] = final_age_efficiencies

            # Контрольный расчет финального среднего по живой когорте
            final_active_mean = np.sum(final_age_efficiencies[active_age_mask]) / n_active_ages

            # Вывод красивой форматированной строки в консоль
            formatted_string = "[" + " ".join([f"{x:.2f}" for x in final_age_efficiencies]) + "]"
            print(formatted_string)
            print(
                f"✅ Успешно построен асимметричный профиль: Год {year} | Вид: {fish.ljust(10)} | Пиковый возраст: {int(peak_age_val)} лет | "
                f"Био-Среднее (по {n_active_ages} возр): {final_active_mean:.2f} | Макс: {np.max(final_age_efficiencies):.2f}")

        print("\n🏁 Полноценный 3D-куб уловистости (10х8х15) успешно сформирован без MCMC за доли секунды!")

    print("\n🏁 Полноценный 3D-куб уловистости (10х8х15) успешно сформирован!")

    # --- Шаг 3: Сборка итогового трехмерного xr.DataArray ---
    output_da = xr.DataArray(
        data=result_matrix,
        coords={
            "Year": years_list,
            "FishType": fish_types,
            "LessAge": catch_3d_filtered.LessAge.values
        },
        dims=["Year", "FishType", "LessAge"],
        name="corrected_catchability_coefficient"
    )

    # Дополнительно переносим подчиненную числовую координату Age для удобства
    output_da = output_da.assign_coords(age=("LessAge", age_numeric_values))

    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    # сохраняем коэффициенты уловистости по возрастам для сети
    output_nc_filename_net = f"{waterbody_name}_catchability_net_3d.nc"
    output_nc_path_net = os.path.join(DATA_STOCK_DIR, output_nc_filename_net)
    output_da.to_netcdf(output_nc_path_net, engine="netcdf4")

    return output_da


# =====================================================================
# ТОЧКА ВХОДА В ПРОГРАММУ
# =====================================================================
if __name__ == '__main__':
    # 2. Запускаем байесовский анализ и получаем трехмерный DataArray
    efficiency_array = calc_catchability_net_3d('zhaysan')

    print("\n--- Результаты успешно сохранены в папке data_stock ")
    # print(efficiency_array)

    # Демонстрация: теперь мы можем удобно делать срезы по получившемуся массиву
    print("\nПроверка среза данных окунь 2021 год:")
    print(efficiency_array.sel(Year=2021, FishType="окунь").to_pandas())
    print("\nПроверка среза данных судак 2022 год:")
    print(efficiency_array.sel(Year=2022, FishType="судак").to_pandas())
    print("\nПроверка среза данных лещ 2024 год:")
    print(efficiency_array.sel(Year=2024, FishType="лещ").to_pandas())
    print("\nПроверка среза данных сазан 2017 год:")
    print(efficiency_array.sel(Year=2017, FishType="сазан").to_pandas())

    efficiency_array = calc_catchability_seine_3d('zhaysan')

    print("\n--- Результаты успешно сохранены в папке data_stock ")
    # print(efficiency_array)

    # Демонстрация: теперь мы можем удобно делать срезы по получившемуся массиву
    print("\nПроверка среза данных окунь 2021 год:")
    print(efficiency_array.sel(Year=2021, FishType="окунь").to_pandas())
    print("\nПроверка среза данных судак 2022 год:")
    print(efficiency_array.sel(Year=2022, FishType="судак").to_pandas())
    print("\nПроверка среза данных лещ 2024 год:")
    print(efficiency_array.sel(Year=2024, FishType="лещ").to_pandas())
    print("\nПроверка среза данных сазан 2017 год:")
    print(efficiency_array.sel(Year=2017, FishType="сазан").to_pandas())
