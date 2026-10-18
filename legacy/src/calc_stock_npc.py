import pandas as pd
import os
import glob
import importlib
import xarray as xr


def calc_stock_npc_3d(waterbody_name: str):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_CATCH_DIR = os.path.join(PROJECT_ROOT, "data_catch")
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    # Ищем файлы строго для конкретного водоема (например: data_catch/balkhash_catch_*.py)
    file_path = os.path.join(DATA_CATCH_DIR, f"{waterbody_name}_npc_assessment.py")
    df_stock_npc = None

    if not file_path:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_catch не найдены.")
        return df_stock_npc

    file_name_tuple = os.path.splitext(os.path.basename(file_path))
    file_name = file_name_tuple[0]  # Чистая строка из кортежа splitext

    try:
        imported_module = importlib.import_module(f"data_catch.{file_name}")
        df_stock_npc = getattr(imported_module, 'data_stock_npc').copy()
        df_stock_npc = df_stock_npc.set_index('Id')
    except Exception as e:
        print(f"[ошибка: ] {e}")

    # 1. Автоматически находим все файлы по маске названия водоема
    file_mask = os.path.join(DATA_CATCH_DIR, f"{waterbody_name}_catch_*.py")
    files = glob.glob(file_mask)

    treated_fish_shared = []
    years_list = []

    for file_path in files:
        # 1. Извлекаем год из имени файла (например, "zhaysan_catch_2016.py" -> 2016)
        file_name = os.path.basename(file_path)
        year = int(file_name.split("_")[-1].split(".")[0])

        # 2. Читаем и выполняем код внутри .py файла
        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()

        local_vars = {"pd": pd}  # Контекст для выполнения кода
        exec(file_content, {}, local_vars)

        # --- НАДЕЖНАЯ ФИЛЬТРАЦИЯ: Ищем строго нужную таблицу по ее имени ---
        target_dataframe_name = f"qty_treated_fish_{year}"

        if target_dataframe_name in local_vars:
            df_catch = local_vars[target_dataframe_name]
        else:
            # Если вдруг имя переменной внутри файла написано с большой буквы или содержит ошибку,
            # ищем любую переменную, которая просто начинается на 'qty_treated_fish_'
            try:
                found_key = next(k for k in local_vars.keys() if k.startswith("qty_treated_fish_"))
                df_catch = local_vars[found_key]
            except StopIteration:
                # Если в файле вообще нет такой таблицы, пропускаем файл и выводим предупреждение
                print(f"В файле {file_name} не найдена таблица, начинающаяся на 'qty_treated_fish_'")
                continue

        # 3. Выделяем рыбу в столбцы, а возрасты оставляем как координаты
        fish_columns = [col for col in df_catch.columns if col not in ["LessAge", "age"]]

        # Конвертируем в 2D DataArray
        da_year = xr.DataArray(
            df_catch[fish_columns].values,
            dims=["LessAge", "FishType"],
            coords={
                "LessAge": df_catch["LessAge"].values,
                "FishType": fish_columns,
                "age": ("LessAge", df_catch["age"].values)
            }
        )

        treated_fish_shared.append(da_year)
        years_list.append(year)

    # Склеиваем все года в один 3D-куб
    treared_fish_shared_3d = xr.concat(treated_fish_shared, dim=pd.Index(years_list, name="Year"), join='outer')

    treared_fish_shared_3d = treared_fish_shared_3d + 1

    # 1. Считаем сумму по возрастам (измерение LessAge схлопнется)
    # Суммируем только уловы, чтобы получить общий объем выборки для каждого вида рыбы в этот год
    treated_fish_shared_sum_age = treared_fish_shared_3d.sum(dim="LessAge")

    # 2. Делим исходный куб на сумму, получая ДОЛИ каждого возраста (нормализация)
    # В результате сумма по оси LessAge для любой рыбы в любой год будет равна 1.0
    treated_fish_shared_normalized_3d = treared_fish_shared_3d / treated_fish_shared_sum_age

    # 3. Переводим вашу готовую таблицу запасов (df_stock) в 2D DataArray
    # Обязательно проверяем, чтобы имена рыб ("лещ", "судак"...) совпадали с колонками в .py файлах
    stock_npc_2d = xr.DataArray(
        df_stock_npc.values,
        dims=["Year", "FishType"],
        coords={
            "Year": df_stock_npc.index.values,
            "FishType": df_stock_npc.columns.values
        }
    )

    # 4. МАТЕМАТИЧЕСКОЕ ПЕРЕМНОЖЕНИЕ
    # Xarray автоматически сопоставит измерения Year и FishType,
    # распределив общий запас по возрастам пропорционально долям уловов!
    final_stock_3d = treated_fish_shared_normalized_3d * stock_npc_2d
    final_stock_3d.name = "yearly_stock_by_age"

    final_stock_3d = final_stock_3d * 1000

    output_nc_filename = f"{waterbody_name}_stock_npc_3d.nc"
    output_nc_path = os.path.join(DATA_STOCK_DIR, output_nc_filename)
    final_stock_3d.to_netcdf(output_nc_path, engine='netcdf4')

    return final_stock_3d


if __name__ == '__main__':
    stock_npc = calc_stock_npc_3d('zhaysan')
    print('сумма по возрастам', stock_npc.sum('LessAge').to_pandas())
    print(type(stock_npc))
