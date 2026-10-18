import os
import sys
import glob
import re
import importlib
import numpy as np
import xarray as xr
from get_fish_prop import get_fish_prop


# ==========================================
# ОСНОВНАЯ ФУНКЦИЯ СБОРКИ 3D ДАННЫХ
# ==========================================
def save_catch_data_3d(waterbody_name):
    """
    Собирает трехмерный массив уловов для указанного водоема за все года.
    Сохраняет результат в data_stock/{waterbody_name}_catch.nc с помощью netCDF4.
    """
    fish_props = get_fish_prop(waterbody_name)
    m1_dict = fish_props['максимальный возраст']

    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_CATCH_DIR = os.path.join(PROJECT_ROOT, "data_catch")
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    os.makedirs(DATA_STOCK_DIR, exist_ok=True)

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема (например: data_catch/balkhash_catch_*.py)
    search_pattern = os.path.join(DATA_CATCH_DIR, f"{waterbody_name}_catch_*.py")
    file_paths = glob.glob(search_pattern)

    if not file_paths:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_catch не найдены.")
        return

    yearly_data_arrays = []
    global_row_counter = 0  # Сквозной счетчик строк для простых Id

    print(f"[СТАРТ] Сборка 3D-массива для водоема: {waterbody_name}...")

    for file_path in file_paths:
        file_name_tuple = os.path.splitext(os.path.basename(file_path))
        file_name = file_name_tuple[0]  # Чистая строка из кортежа splitext

        if file_name == "__init__":
            continue

        # Находим год в названии файла
        year_match = re.search(r"\d{4}", file_name)
        if not year_match:
            continue
        year_str = year_match.group()

        try:
            # Динамический импорт модуля
            imported_module = importlib.import_module(f"data_catch.{file_name}")

            catch_var_name = file_name
            shares_var_name = f"qty_treated_fish_{year_str}"

            df_catch_raw = getattr(imported_module, catch_var_name).copy()
            df_shares_raw = getattr(imported_module, shares_var_name).copy()

            # --- РАСЧЕТ ДОЛЕЙ И ПЕРЕСТРОЕНИЕ ИНДЕКСОВ ВОЗРАСТОВ ---
            df_shares_raw = df_shares_raw.set_index("LessAge")
            series_numeric_ages = df_shares_raw["age"].astype(int)
            df_shares_fish_only = df_shares_raw.drop(columns=["age"])

            # 1. Извлекаем числовую часть из индексов типа 'less_2', 'less_3'...'less_16'
            age_numbers = df_shares_fish_only.index.str.split("_").str[1].astype(int)

            # 2. Проходим циклом по колонкам (видам рыб), которые есть в датафрейме
            for fish in df_shares_fish_only.columns:
                # Проверяем, задан ли максимальный возраст для этой рыбы в словаре
                if fish in m1_dict:
                    max_age = m1_dict[fish]

                    # Строим индивидуальную маску для текущей рыбы:
                    # Возраст должен быть от 3 до индивидуального максимума включительно
                    mask = age_numbers <= max_age

                    # Прибавляем единицу только в столбец этой рыбы по её маске
                    df_shares_fish_only.loc[mask, fish] = df_shares_fish_only.loc[mask, fish] + 1
                else:
                    print(
                        f"Предупреждение: Рыба '{fish}' отсутствует в словаре максимальных возрастов."
                    )

            # Нормализация долей возрастов по каждому виду рыбы
            species_sums = df_shares_fish_only.sum(axis=0).replace(0, 1.0)
            df_shares_normalized = df_shares_fish_only.div(species_sums, axis=1)
            df_shares_final = df_shares_normalized.T

            # Пересечение видов рыб
            common_species = list(set(df_catch_raw.columns).intersection(set(df_shares_final.index)))
            if not common_species:
                print(f" [!] В файле {file_name} нет общих видов рыб. Пропуск.")
                continue
            common_species.sort()

            # --- ГЕНЕРАЦИЯ ПРОСТЫХ СКВОЗНЫХ Id ---
            num_rows = len(df_catch_raw)
            id_list = [str(global_row_counter + i) for i in range(num_rows)]
            global_row_counter += num_rows

            df_catch_raw['Id'] = id_list

            # Выделяем метаданные
            df_meta = df_catch_raw.set_index('Id')[
                ['Date', 'Place', 'Instrument', 'Instrument_size', 'CatchType', 'Year', 'Area']]

            # Фильтруем таблицы по общему списку видов рыб
            df_catch_filtered = df_catch_raw.set_index('Id')[common_species]
            df_shares_filtered = df_shares_final.loc[common_species]

            # Очищаем типы координат под netCDF4
            less_ages_list = [str(x) for x in df_shares_filtered.columns.tolist()]
            species_coords_list = [str(x) for x in common_species]

            # --- ВНЕШНЕЕ УМНОЖЕНИЕ (OUTER PRODUCT) ---
            matrix_catch = df_catch_filtered.to_numpy().astype(float)
            matrix_shares = df_shares_filtered.to_numpy().astype(float)

            array_3d_year = matrix_catch[:, :, np.newaxis] * matrix_shares[np.newaxis, :, :]

            # Оборачиваем в xarray.DataArray с осями FishType и LessAge
            da_year = xr.DataArray(
                array_3d_year,
                coords=[id_list, species_coords_list, less_ages_list],
                dims=["Id", "FishType", "LessAge"]
            )

            # Переменная CatchType сохранена без изменений названия
            da_year = da_year.assign_coords(
                Date=('Id', df_meta['Date'].values.astype(object)),
                Place=('Id', df_meta['Place'].values.astype(object)),
                Instrument=('Id', df_meta['Instrument'].values.astype(object)),
                Instrument_size=('Id', df_meta['Instrument_size'].values.astype(int)),
                CatchType=('Id', df_meta['CatchType'].values.astype(object)),
                Year=('Id', df_meta['Year'].values.astype(int)),
                Area=("Id", df_meta["Area"].values.astype(object))
            )

            # Привязываем числовые значения возрастов к текстовой оси 'LessAge'
            da_year = da_year.assign_coords(
                age=('LessAge', series_numeric_ages.loc[less_ages_list].values.astype(int))
            )

            yearly_data_arrays.append(da_year)
            print(f" -> Год {year_str} успешно обработан.")

        except Exception as e:
            print(f" [Ошибка] Не удалось обработать файл {file_name}: {e}")

    # ==========================================
    # 3. ОБЪЕДИНЕНИЕ ВСЕХ ГОДОВ И ЭКСПОРТ В NetCDF
    # ==========================================
    if yearly_data_arrays:
        print("\nОбъединение годовых массивов...")
        da_final_3d = xr.concat(yearly_data_arrays, dim="Id", join='outer')
        da_final_3d.name = "catch_volume"

        print("\n=== АРХИТЕКТУРА ИТОГОВОГО МАССИВА ===")
        print(da_final_3d)

        # Динамический путь сохранения: {название водоема}_catch.nc
        output_nc_filename_net = f"{waterbody_name}_catch_net_3d.nc"
        output_nc_filename_seine = f"{waterbody_name}_catch_seine_3d.nc"
        output_nc_path_net = os.path.join(DATA_STOCK_DIR, output_nc_filename_net)
        output_nc_path_seine = os.path.join(DATA_STOCK_DIR, output_nc_filename_seine)

        # Сохраняем в два файла по сети и по неводу
        da_final_3d_net = da_final_3d.sel(Instrument='сеть')
        # 2. Создаем новый массив чисел от 1 до количества оставшихся строк
        new_ids = np.arange(1, len(da_final_3d_net.Id) + 1)
        # 3. Назначаем новый индекс и переводим в pandas
        da_final_3d_net = da_final_3d_net.assign_coords(Id=new_ids)

        da_final_3d_seine = da_final_3d.sel(Instrument='невод')
        # 2. Создаем новый массив чисел от 1 до количества оставшихся строк
        new_ids = np.arange(1, len(da_final_3d_seine.Id) + 1)
        # 3. Назначаем новый индекс и переводим в pandas
        da_final_3d_seine = da_final_3d_seine.assign_coords(Id=new_ids)

        da_final_3d_net.to_netcdf(output_nc_path_net, engine="netcdf4")
        da_final_3d_seine.to_netcdf(output_nc_path_seine, engine="netcdf4")

        print("\n" + "=" * 50)
        print(f" [УСПЕХ] Файл с многомерными уловами сохранен!")
        print(f" Итоговые оси: Id, FishType, LessAge")
        print(f" Путь к файлам: {output_nc_path_net}   {output_nc_path_seine}")
        print(da_final_3d_net.shape, da_final_3d_net.dims)
        print(da_final_3d_seine.shape, da_final_3d_seine.dims)
        print(da_final_3d_net.FishType.values)
        print(da_final_3d_net.sel(Year=2015).sum('LessAge').to_pandas())
        print("=" * 50)
    else:
        print("\n [!] Данные отсутствуют. Сохранение отменено.")


# --- ТЕСТОВЫЙ ЗАПУСК ВНУТРИ МОДУЛЯ ---
if __name__ == "__main__":
    save_catch_data_3d(waterbody_name="zhaysan")
