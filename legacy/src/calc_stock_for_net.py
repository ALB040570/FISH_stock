import os
import numpy as np
import xarray as xr
from model_for_net import calc_model_for_net
from get_fish_prop import get_fish_prop
from get_catch_3d import get_catch_net_3d
from get_catchability_3d import get_catchability_net_3d

# Рассчитывает запас альтернативным алгоритмом
def calc_stock_net(
    real_caught_count, k_catchability, fish_speed, hours, net_width, lake_area
):
    """
    Вычисляет абсолютные запасы рыбы в водоеме на основе альтернативной методики для пассивных орудий лова
    k_catchability: коэффициент уловистости
    hours: время стоянки сети
    net_width: длина сети
    fish_speed: скорость блуждания рыбы
    real_caught_count: объем вылова
    lake_area: площадь водоема
    """

    # Вызываем функцию ядра, забирая только второй аргумент
    _, final_state = calc_model_for_net(
        k_catchability=k_catchability, hours=hours, net_width=net_width, fish_speed=fish_speed
    )

    net_share = final_state["Сеть"]

    # Геометрия первой области
    r0 = net_width / 2.0
    r1 = fish_speed
    s1_relative = (r1**2) - (r0**2)

    # Расчет Х: доля рыб в сети * площадь первого кольца
    X = net_share * s1_relative

    if X == 0:
        return 0.0

    # Запас = 1/Х * Реальная площадь водоема * Количество пойманных рыб
    total_stock = (1.0 / X) * lake_area * real_caught_count

    # return {
    #     "Коэффициент уловистости (k)": k_catchability,
    #     "Ширина сети": net_width,
    #     "Доля вылова по модели (net_share)": round(net_share, 4),
    #     "Вспомогательный индекс X": round(X, 4),
    #     "Реальная площадь водоема (кв.м)": lake_area,
    #     "Фактический улов (шт)": real_caught_count,
    #     "stock_in_pieces": round(total_stock, 1),
    # }

    return round(total_stock, 1)

# Рассчитывает и сохраняет в файл запас без учета возрастов для всех уловов
def calc_stocks_net_out_ages(waterbody_name: str):
    fish_props = get_fish_prop(waterbody_name)
    square_by_years_dict = fish_props['площадь водоема']
    # переводим площади в квадратные метры
    square_by_years_dict = {k: v * 1000000 for k, v in square_by_years_dict.items()}
    time_net_hour_dict = fish_props['время стоянки сети']
    v_cr_dict = fish_props['скорость рыбы']
    # переводим скорости рыб в м/час
    v_dict = {k: v * 3600 for k, v in v_cr_dict.items()}
    k_catchability_dict = fish_props['коэффициент уловистости сети']
    net_length_dict = fish_props['длина сети']

    catch_3d = get_catch_net_3d(waterbody_name)

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
    fish_in_dictionary = list(v_dict.keys())
    catch_2d_filtered = catch_2d.sel(FishType=catch_2d.FishType.isin(fish_in_dictionary))

    # ВЫРАВНИВАНИЕ ПО ГОДАМ:
    # Берем массив лет для каждого Id (da_filtered.Year.values) и
    # превращаем его в массивы нужных параметров той же длины, что и Id.
    ids_years = catch_2d_filtered.Year.values

    id_net_length = np.array([net_length_dict[yr] for yr in ids_years])
    id_lake_square = np.array([square_by_years_dict[yr] for yr in ids_years])
    id_time_net_hour = np.array([time_net_hour_dict[yr] for yr in ids_years])

    # Создаем DataArray для этих параметров, привязав их строго к измерению 'Id'
    net_length_da = xr.DataArray(id_net_length, coords={'Id': catch_2d_filtered.Id}, dims=['Id'])
    lake_square_da = xr.DataArray(id_lake_square, coords={'Id': catch_2d_filtered.Id}, dims=['Id'])
    time_net_hour_da = xr.DataArray(id_time_net_hour, coords={'id': catch_2d_filtered.Id}, dims=['Id'])

    # Выравнивание скоростей рыб
    fish_speed_da = xr.DataArray(
        [v_dict[fish] for fish in catch_2d_filtered.FishType.values],
        coords={'FishType': catch_2d_filtered.FishType.values},
        dims=['FishType']
    )

    # Выравнивание коэффициенты уловистости рыб
    k_catchability_da = xr.DataArray(
        [k_catchability_dict[fish] for fish in catch_2d_filtered.FishType.values],
        coords={'FishType': catch_2d_filtered.FishType.values},
        dims=['FishType']
    )

    stock_da = xr.apply_ufunc(
        calc_stock_net,
        catch_2d_filtered,
        k_catchability_da,
        fish_speed_da,
        time_net_hour_da,
        net_length_da,
        lake_square_da,
        input_core_dims=[[]] * 6,  # Указываем, что на вход функция принимает скаляры (0 размерностей)
        output_core_dims=[[]],  # На выходе из функции тоже получается скаляр
        vectorize=True,  # КЛЮЧЕВОЙ ФЛАГ: заставляет numpy запустить цикл по всем ячейкам
        output_dtypes=[float]  # Тип данных, который вернет функция
    )

    # print('stock_da = ', stock_da)
    # превращаем рассчитанные запасы в трехмерный массив
    stock_da_3d = stock_da * catch_3d_shares
    print(stock_da_3d.shape, stock_da_3d.dims)
    print('raznost = ', stock_da_3d.sum('LessAge') - stock_da)

    # сохраняем запасы без учета возрастов
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")
    output_nc_filename_net = f"{waterbody_name}_stock_net_out_ages_3d.nc"
    output_nc_path_net = os.path.join(DATA_STOCK_DIR, output_nc_filename_net)
    stock_da_3d.to_netcdf(output_nc_path_net, engine="netcdf4")


# Рассчитывает и сохраняет в файл запас с учетом возрастов для всех уловов
def calc_stocks_net_with_ages(waterbody_name: str):
    fish_props = get_fish_prop(waterbody_name)
    square_by_years_dict = fish_props['площадь водоема']
    # переводим площади в квадратные метры
    square_by_years_dict = {k: v * 1000000 for k, v in square_by_years_dict.items()}
    time_net_hour_dict = fish_props['время стоянки сети']
    v_cr_dict = fish_props['скорость рыбы']
    # переводим скорости рыб в м/час
    v_dict = {k: v * 3600 for k, v in v_cr_dict.items()}
    net_length_dict = fish_props['длина сети']

    # извлекаем трехмерный коэффициент уловистости
    k_catchability = get_catchability_net_3d(waterbody_name)

    # извлекаем трехмерные запасы
    catch_3d = get_catch_net_3d(waterbody_name)

    # Фильтруем виды рыб
    fish_in_dictionary = list(v_dict.keys())
    fish_in_catchability = list(k_catchability.FishType.values)
    common_fish_list = list(set(fish_in_dictionary) & set(fish_in_catchability))
    catch_3d_filtered = catch_3d.sel(FishType=common_fish_list)

    # 1. Вытаскиваем массивы Id, Date и Year целиком
    ids_list = catch_3d_filtered.Id.values
    years_list = catch_3d_filtered.Year.values

    # 2. Создаем быстрые справочники (словари) {Id: Значение}
    # id_to_date = dict(zip(ids_list, dates_list))
    id_to_year = dict(zip(ids_list, years_list))

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
        Place=("Id", catch_3d_filtered.Place.values), CatchType=('Id', catch_3d_filtered.CatchType.values)
    )

    stock_da = stock_da.assign_coords(
        age=("LessAge", catch_3d_filtered.age.values)
    )

    for current_id in ids_list:
        for current_fish in common_fish_list:
            for current_age in catch_3d_filtered.LessAge.values:
                current_stock = calc_stock_net(
                                    catch_3d_filtered.loc[current_id, current_fish, current_age].values,
                                    k_catchability.loc[id_to_year[current_id], current_fish, current_age].values,
                                    v_dict[current_fish],
                                    time_net_hour_dict[id_to_year[current_id]],
                                    net_length_dict[id_to_year[current_id]],
                                    square_by_years_dict[id_to_year[current_id]]
                )
                stock_da.loc[dict(Id=current_id, FishType=current_fish, LessAge=current_age)] = current_stock

        print(f'посчитано {current_id} строк')
        # print(stock_da.loc[current_id, :, :])

    # сохраняем запасы с учетом возрастов
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")
    output_nc_filename_net = f"{waterbody_name}_stock_net_with_ages_3d.nc"
    output_nc_path_net = os.path.join(DATA_STOCK_DIR, output_nc_filename_net)
    stock_da.to_netcdf(output_nc_path_net, engine="netcdf4")





if __name__ == "__main__":
    # Тестовые параметры
    K_VALUE = 0.3
    HOURS_VALUE = 12
    NET_W = 25.0
    FISH_V = 400.0
    RESERVOIR_SQ = 3000000000.0
    REAL_CATCH_FISH = 10

    stock_report = calc_stock_net(
        k_catchability=K_VALUE,
        hours=HOURS_VALUE,
        net_width=NET_W,
        fish_speed=FISH_V,
        real_caught_count=REAL_CATCH_FISH,
        lake_area=RESERVOIR_SQ,
    )

    print("=== РЕЗУЛЬТАТ ОЦЕНКИ ПОПУЛЯЦИИ ===")
    print(stock_report)

    calc_stocks_net_with_ages('zhaysan')
    calc_stocks_net_out_ages('zhaysan')

