import os
import numpy as np
import xarray as xr

from data_catch.zhaysan_fish_prop import k_catchability_2
from get_fish_prop import get_fish_prop
from get_catch_3d import get_catch_seine_3d
from get_catchability_3d import get_catchability_seine_3d


def calc_stocks_seine_out_ages(waterbody_name: str):
    fish_props = get_fish_prop(waterbody_name)
    square_by_years_dict = fish_props['площадь водоема']
    # переводим площади в квадратные метры
    square_by_years_dict = {k: v * 1000000 for k, v in square_by_years_dict.items()}
    # k_catchability = get_catchability_seine_3d(waterbody_name)
    k_catchability_dict = fish_props['коэффициент уловистости невода']

    catch_3d = get_catch_seine_3d(waterbody_name)

    # Считаем сумму уловов по оси возраста 'LessAge'
    # На выходе получаем 2D-куб с суммами для каждой комбинации [Id, FishType]
    catch_2d = catch_3d.sum(dim="LessAge")

    # Защита от деления на ноль: заменяем все нулевые суммы на 1.0
    # (В ячейках с нулевым уловом деление на 1.0 оставит корректный 0.0)
    catch_2d_safe = catch_2d.where(catch_2d != 0, 1.0)

    # Вычисляем долю: делим исходный 3D-массив на массив безопасных сумм
    catch_3d_shares = catch_3d / catch_2d_safe

    # Переименуем переменную внутри массива для наглядности (опционально)
    catch_3d_shares.name = "catch_shares"

    # Фильтруем виды рыб
    fish_in_dictionary = list(k_catchability_dict)
    catch_2d_filtered = catch_2d.sel(FishType=catch_2d.FishType.isin(fish_in_dictionary))

    ids_years = catch_2d_filtered.Year.values
    id_lake_square = np.array([square_by_years_dict[yr] for yr in ids_years])

    # Создаем DataArray для этих параметров, привязав их строго к измерению 'Id'
    lake_square_da = xr.DataArray(id_lake_square, coords={'Id': catch_2d_filtered.Id}, dims=['Id'])

    # 1. Вытаскиваем массивы Id и Year целиком
    ids_list = catch_2d_filtered.Id.values
    years_list = catch_2d_filtered.Year.values
    area_list = catch_2d_filtered.Area.values

    # 2. Создаем быстрые справочники (словари) {Id: Значение}
    id_to_year = dict(zip(ids_list, years_list))
    id_to_area = dict(zip(ids_list, area_list))

    empty_matrix = np.zeros(
        (len(ids_list), len(catch_2d_filtered.FishType.values)),
        dtype=np.float64
    )

    # 3. Упаковываем её в xr.DataArray и сразу привязываем подчиненные координаты
    stock_da = xr.DataArray(
        data=empty_matrix,
        coords={
            "Id": ids_list,
            "FishType": catch_2d_filtered.FishType.values,
        },
        dims=["Id", "FishType"],
    )

    # Подтягиваем подчиненные колонки Date и Year из исходного массива уловов
    stock_da = stock_da.assign_coords(
        Year=("Id", catch_2d_filtered.Year.values), Date=("Id", catch_2d_filtered.Date.values),
        Place=("Id", catch_2d_filtered.Place.values), Area=("Id", catch_2d_filtered.Area.values),
        CatchType=('Id', catch_2d_filtered.CatchType.values)
    )

    for current_id in ids_list:
        for current_fish in catch_2d_filtered.FishType.values:
            ulov = catch_2d_filtered.loc[current_id, current_fish]
            square = id_to_area[current_id] * 10000
            total_square = square_by_years_dict[id_to_year[current_id]]
            k_catchability_cur = k_catchability_dict[current_fish]
            current_stock = ulov / (k_catchability_cur * square) * total_square
            stock_da.loc[dict(Id=current_id, FishType=current_fish)] = current_stock
        print(f'посчитано {current_id} строк без учета возрастов')

    # превращаем рассчитанные запасы в трехмерный массив
    stock_da_3d = stock_da * catch_3d_shares
    # print(stock_da_3d.shape, stock_da_3d.dims)
    # print('raznost = ', stock_da_3d.sum('LessAge') - stock_da)

    # сохраняем запасы без учета возрастов
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")
    output_nc_filename_net = f"{waterbody_name}_stock_seine_out_ages_3d.nc"
    output_nc_path_net = os.path.join(DATA_STOCK_DIR, output_nc_filename_net)
    stock_da_3d.to_netcdf(output_nc_path_net, engine="netcdf4")

def calc_stocks_seine_with_ages(waterbody_name: str):
    fish_props = get_fish_prop(waterbody_name)
    square_by_years_dict = fish_props['площадь водоема']
    # переводим площади в квадратные метры
    square_by_years_dict = {k: v * 1000000 for k, v in square_by_years_dict.items()}
    k_catchability = get_catchability_seine_3d(waterbody_name)

    catch_3d = get_catch_seine_3d(waterbody_name)

    # Фильтруем виды рыб
    fish_in_dictionary = list(k_catchability.FishType.values)
    catch_3d_filtered = catch_3d.sel(FishType=catch_3d.FishType.isin(fish_in_dictionary))

    ids_years = catch_3d_filtered.Year.values
    id_lake_square = np.array([square_by_years_dict[yr] for yr in ids_years])

    # Создаем DataArray для этих параметров, привязав их строго к измерению 'Id'
    lake_square_da = xr.DataArray(id_lake_square, coords={'Id': catch_3d_filtered.Id}, dims=['Id'])

    # 1. Вытаскиваем массивы Id и Year целиком
    ids_list = catch_3d_filtered.Id.values
    years_list = catch_3d_filtered.Year.values
    area_list = catch_3d_filtered.Area.values

    # 2. Создаем быстрые справочники (словари) {Id: Значение}
    id_to_year = dict(zip(ids_list, years_list))
    id_to_area = dict(zip(ids_list, area_list))

    empty_matrix = np.zeros(
        (len(ids_list), len(catch_3d_filtered.FishType.values), len(catch_3d_filtered.LessAge.values)),
        dtype=np.float64
    )

    # Упаковываем её в xr.DataArray и сразу привязываем подчиненные координаты
    stock_da = xr.DataArray(
        data=empty_matrix,
        coords={
            "Id": ids_list,
            "FishType": catch_3d_filtered.FishType.values,
            "LessAge": catch_3d_filtered.LessAge.values,
        },
        dims=["Id", "FishType", "LessAge"],
    )

    # Подтягиваем подчиненные колонки Date и Year из исходного массива уловов
    stock_da = stock_da.assign_coords(
        Year=("Id", catch_3d_filtered.Year.values), Date=("Id", catch_3d_filtered.Date.values),
        Place=("Id", catch_3d_filtered.Place.values), Area=("Id", catch_3d_filtered.Area.values),
        CatchType=('Id', catch_3d_filtered.CatchType.values)
    )

    stock_da = stock_da.assign_coords(
        age=("LessAge", catch_3d_filtered.age.values)
    )

    for current_id in ids_list:
        square = id_to_area[current_id] * 10000
        total_square = square_by_years_dict[id_to_year[current_id]]
        for current_fish in catch_3d_filtered.FishType.values:
            for current_age in catch_3d_filtered.LessAge.values:
                current_catch = catch_3d_filtered.loc[current_id, current_fish, current_age]
                k_catchability_cur = k_catchability.loc[id_to_year[current_id], current_fish, current_age].values
                current_stock = current_catch / (k_catchability_cur * square) * total_square
                stock_da.loc[dict(Id=current_id, FishType=current_fish, LessAge=current_age)] = current_stock
        print(f'посчитано {current_id} строк с учетом возрастов')

    # сохраняем запасы без учета возрастов
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")
    output_nc_filename_net = f"{waterbody_name}_stock_seine_with_ages_3d.nc"
    output_nc_path_net = os.path.join(DATA_STOCK_DIR, output_nc_filename_net)
    stock_da.to_netcdf(output_nc_path_net, engine="netcdf4")



if __name__ == '__main__':
    calc_stocks_seine_out_ages('zhaysan')
    calc_stocks_seine_with_ages('zhaysan')


