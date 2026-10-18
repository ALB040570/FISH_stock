import os
import xarray as xr
import numpy as np
from get_catch_3d import get_catch_net_3d, get_catch_seine_3d
from get_catchability_3d import get_catchability_net_3d, get_catchability_seine_3d
from get_fish_prop import get_fish_prop
from calc_stock_for_net import calc_stock_net


def calc_yearly_stock_net_out_ages_on_catch_3d(waterbody_name: str):
    fish_props = get_fish_prop(waterbody_name)
    square_by_years_dict = fish_props['площадь водоема']
    # переводим площадь в квадратные метры
    square_by_years_dict = {k: v * 1000000 for k, v in square_by_years_dict.items()}
    time_net_hour_dict = fish_props['время стоянки сети']
    v_cr_dict = fish_props['скорость рыбы']
    # переводим скорости рыб в м/час
    v_dict = {k: v * 3600 for k, v in v_cr_dict.items()}
    k_catchability_dict = fish_props['коэффициент уловистости сети']
    net_length_dict = fish_props['длина сети']

    catch_net_3d = get_catch_net_3d(waterbody_name)
    catch_net_3d_nauch = catch_net_3d.sel(CatchType='научный')
    catch_net_3d_prom = catch_net_3d.sel(CatchType='промысловый')

    # Сгруппируем массивы по Year по измерению 'Id'
    grouped_means_nauch = (
        catch_net_3d_nauch.groupby(xr.DataArray(catch_net_3d_nauch.Year, dims="Id", name="Year")).mean(dim="Id")
    )

    grouped_means_prom = (
        catch_net_3d_prom.groupby(xr.DataArray(catch_net_3d_prom.Year, dims="Id", name="Year")).mean(dim="Id")
    )

    grouped_count_nauch= (
        catch_net_3d_nauch.groupby(xr.DataArray(catch_net_3d_nauch.Year, dims='Id', name='Year')).count(dim='Id')
    )

    grouped_count_prom = (
        catch_net_3d_prom.groupby(xr.DataArray(catch_net_3d_prom.Year, dims='Id', name='Year')).count(dim='Id')
    )

    # Находим полный (объединенный) список всех уникальных годов из обоих массивов
    all_years = np.union1d(grouped_means_nauch.Year.values, grouped_means_prom.Year.values)

    # Принудительно приводим все массивы к общему списку годов, заполняя пропуски нулями
    grouped_means_nauch = grouped_means_nauch.reindex(Year=all_years, fill_value=0.0)
    grouped_count_nauch = grouped_count_nauch.reindex(Year=all_years, fill_value=0.0)

    grouped_means_prom = grouped_means_prom.reindex(Year=all_years, fill_value=0.0)
    grouped_count_prom = grouped_count_prom.reindex(Year=all_years, fill_value=0.0)

    # 3. Считаем сумму весов (теперь деление на ноль безопасно, так как xarray вернет NaN там, где сумма 0)
    total_count = grouped_count_nauch + grouped_count_prom

    weight_nauch = grouped_count_nauch / total_count
    weight_prom = grouped_count_prom / total_count

    # 4. Если в какой-то год не было вообще никаких ловов (сумма весов 0),
    # деление даст NaN. Заменяем эти NaN на 0, чтобы не испортить формулу
    weight_nauch = weight_nauch.fillna(0.0)
    weight_prom = weight_prom.fillna(0.0)

    # Фильтруем виды рыб
    fish_in_dictionary = list(v_dict.keys())
    fish_in_catchability = list(k_catchability_dict.keys())
    common_fish_list = list(set(fish_in_dictionary) & set(fish_in_catchability))
    grouped_means_nauch_filtered = grouped_means_nauch.sel(FishType=common_fish_list)
    grouped_means_prom_filtered = grouped_means_prom.sel(FishType=common_fish_list)

    empty_matrix_nauch = np.zeros(
        (len(all_years), len(grouped_means_nauch_filtered.FishType.values), len(grouped_means_nauch_filtered.LessAge.values)),
        dtype=np.float64
    )

    # Упаковываем её в xr.DataArray и сразу привязываем подчиненные координаты
    stock_da_nauch = xr.DataArray(
        data=empty_matrix_nauch,
        coords={
            "Year": all_years,
            "FishType": grouped_means_nauch_filtered.FishType.values,
            "LessAge": grouped_means_nauch_filtered.LessAge.values,
        },
        dims=["Year", "FishType", "LessAge"],
    )

    stock_da_nauch = stock_da_nauch.assign_coords(
        age=("LessAge", grouped_means_nauch_filtered.age.values)
    )

    for current_id in all_years:
        for current_fish in common_fish_list:
            for current_age in grouped_means_nauch_filtered.LessAge.values:
                current_stock = calc_stock_net(
                                    grouped_means_nauch_filtered.loc[current_id, current_fish, current_age].values,
                                    k_catchability_dict[current_fish],
                                    v_dict[current_fish],
                                    time_net_hour_dict[current_id],
                                    net_length_dict[current_id],
                                    square_by_years_dict[current_id]
                )
                stock_da_nauch.loc[dict(Year=current_id, FishType=current_fish, LessAge=current_age)] = current_stock

        print(f'посчитано для {current_id} года для научного лова')
        # print(stock_da_nauch.loc[current_id, :, :])

    empty_matrix_prom = np.zeros(
        (len(all_years), len(grouped_means_prom_filtered.FishType.values), len(grouped_means_prom_filtered.LessAge.values)),
        dtype=np.float64
    )

    # Упаковываем её в xr.DataArray и сразу привязываем подчиненные координаты
    stock_da_prom = xr.DataArray(
        data=empty_matrix_prom,
        coords={
            "Year": all_years,
            "FishType": grouped_means_prom_filtered.FishType.values,
            "LessAge": grouped_means_prom_filtered.LessAge.values,
        },
        dims=["Year", "FishType", "LessAge"],
    )

    stock_da_prom = stock_da_prom.assign_coords(
        age=("LessAge", grouped_means_prom_filtered.age.values)
    )

    for current_id in all_years:
        for current_fish in common_fish_list:
            for current_age in grouped_means_prom_filtered.LessAge.values:
                current_stock = calc_stock_net(
                                    grouped_means_prom_filtered.loc[current_id, current_fish, current_age].values,
                                    k_catchability_dict[current_fish],
                                    v_dict[current_fish],
                                    time_net_hour_dict[current_id],
                                    net_length_dict[current_id],
                                    square_by_years_dict[current_id]
                )
                stock_da_prom.loc[dict(Year=current_id, FishType=current_fish, LessAge=current_age)] = current_stock

        print(f'посчитано для {current_id} года для промыслового лова')
        # print(stock_da_prom.loc[current_id, :, :])

    # Считаем финальный результат (теперь координаты Year идеально совпадают)
    yearly_stock_net_out_ages_on_catch = weight_nauch * stock_da_nauch + weight_prom * stock_da_prom

    # сохраняем запасы без учета возрастов
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")
    output_nc_filename_net = f"{waterbody_name}_yearly_stock_net_out_ages_on_catch_3d.nc"
    output_nc_path_net = os.path.join(DATA_STOCK_DIR, output_nc_filename_net)
    yearly_stock_net_out_ages_on_catch.to_netcdf(output_nc_path_net, engine="netcdf4")

    return yearly_stock_net_out_ages_on_catch


def calc_yearly_stock_net_with_ages_on_catch_3d(waterbody_name: str):
    fish_props = get_fish_prop(waterbody_name)
    square_by_years_dict = fish_props['площадь водоема']
    # переводим площадь в квадратные метры
    square_by_years_dict = {k: v * 1000000 for k, v in square_by_years_dict.items()}
    time_net_hour_dict = fish_props['время стоянки сети']
    v_cr_dict = fish_props['скорость рыбы']
    # переводим скорости рыб в м/час
    v_dict = {k: v * 3600 for k, v in v_cr_dict.items()}
    net_length_dict = fish_props['длина сети']
    k_catchability = get_catchability_net_3d(waterbody_name)

    catch_net_3d = get_catch_net_3d(waterbody_name)
    catch_net_3d_nauch = catch_net_3d.sel(CatchType='научный')
    catch_net_3d_prom = catch_net_3d.sel(CatchType='промысловый')

    # Сгруппируем массивы по Year по измерению 'Id'
    grouped_means_nauch = (
        catch_net_3d_nauch.groupby(xr.DataArray(catch_net_3d_nauch.Year, dims="Id", name="Year")).mean(dim="Id")
    )

    grouped_means_prom = (
        catch_net_3d_prom.groupby(xr.DataArray(catch_net_3d_prom.Year, dims="Id", name="Year")).mean(dim="Id")
    )

    grouped_count_nauch= (
        catch_net_3d_nauch.groupby(xr.DataArray(catch_net_3d_nauch.Year, dims='Id', name='Year')).count(dim='Id')
    )

    grouped_count_prom = (
        catch_net_3d_prom.groupby(xr.DataArray(catch_net_3d_prom.Year, dims='Id', name='Year')).count(dim='Id')
    )

    # Находим полный (объединенный) список всех уникальных годов из обоих массивов
    all_years = np.union1d(grouped_means_nauch.Year.values, grouped_means_prom.Year.values)

    # Принудительно приводим все массивы к общему списку годов, заполняя пропуски нулями
    grouped_means_nauch = grouped_means_nauch.reindex(Year=all_years, fill_value=0.0)
    grouped_count_nauch = grouped_count_nauch.reindex(Year=all_years, fill_value=0.0)

    grouped_means_prom = grouped_means_prom.reindex(Year=all_years, fill_value=0.0)
    grouped_count_prom = grouped_count_prom.reindex(Year=all_years, fill_value=0.0)

    # 3. Считаем сумму весов (теперь деление на ноль безопасно, так как xarray вернет NaN там, где сумма 0)
    total_count = grouped_count_nauch + grouped_count_prom

    weight_nauch = grouped_count_nauch / total_count
    weight_prom = grouped_count_prom / total_count

    # 4. Если в какой-то год не было вообще никаких ловов (сумма весов 0),
    # деление даст NaN. Заменяем эти NaN на 0, чтобы не испортить формулу
    weight_nauch = weight_nauch.fillna(0.0)
    weight_prom = weight_prom.fillna(0.0)

    # Фильтруем виды рыб
    fish_in_dictionary = list(v_dict.keys())
    fish_in_catchability = k_catchability.FishType.values
    common_fish_list = list(set(fish_in_dictionary) & set(fish_in_catchability))
    grouped_means_nauch_filtered = grouped_means_nauch.sel(FishType=common_fish_list)
    grouped_means_prom_filtered = grouped_means_prom.sel(FishType=common_fish_list)

    empty_matrix_nauch = np.zeros(
        (len(all_years), len(grouped_means_nauch_filtered.FishType.values), len(grouped_means_nauch_filtered.LessAge.values)),
        dtype=np.float64
    )

    # Упаковываем её в xr.DataArray и сразу привязываем подчиненные координаты
    stock_da_nauch = xr.DataArray(
        data=empty_matrix_nauch,
        coords={
            "Year": all_years,
            "FishType": grouped_means_nauch_filtered.FishType.values,
            "LessAge": grouped_means_nauch_filtered.LessAge.values,
        },
        dims=["Year", "FishType", "LessAge"],
    )

    stock_da_nauch = stock_da_nauch.assign_coords(
        age=("LessAge", grouped_means_nauch_filtered.age.values)
    )

    for current_id in all_years:
        for current_fish in common_fish_list:
            for current_age in grouped_means_nauch_filtered.LessAge.values:
                current_stock = calc_stock_net(
                                    grouped_means_nauch_filtered.loc[current_id, current_fish, current_age].values,
                                    k_catchability.loc[current_id, current_fish, current_age].values,
                                    v_dict[current_fish],
                                    time_net_hour_dict[current_id],
                                    net_length_dict[current_id],
                                    square_by_years_dict[current_id]
                )
                stock_da_nauch.loc[dict(Year=current_id, FishType=current_fish, LessAge=current_age)] = current_stock

        print(f'посчитано для {current_id} года для научного лова')
        # print(stock_da_nauch.loc[current_id, :, :])

    empty_matrix_prom = np.zeros(
        (len(all_years), len(grouped_means_prom_filtered.FishType.values), len(grouped_means_prom_filtered.LessAge.values)),
        dtype=np.float64
    )

    # Упаковываем её в xr.DataArray и сразу привязываем подчиненные координаты
    stock_da_prom = xr.DataArray(
        data=empty_matrix_prom,
        coords={
            "Year": all_years,
            "FishType": grouped_means_prom_filtered.FishType.values,
            "LessAge": grouped_means_prom_filtered.LessAge.values,
        },
        dims=["Year", "FishType", "LessAge"],
    )

    stock_da_nauch = stock_da_nauch.assign_coords(
        age=("LessAge", grouped_means_prom_filtered.age.values)
    )

    for current_id in all_years:
        for current_fish in common_fish_list:
            for current_age in grouped_means_prom_filtered.LessAge.values:
                current_stock = calc_stock_net(
                                    grouped_means_prom_filtered.loc[current_id, current_fish, current_age].values,
                                    k_catchability.loc[current_id, current_fish, current_age].values,
                                    v_dict[current_fish],
                                    time_net_hour_dict[current_id],
                                    net_length_dict[current_id],
                                    square_by_years_dict[current_id]
                )
                stock_da_prom.loc[dict(Year=current_id, FishType=current_fish, LessAge=current_age)] = current_stock

        print(f'посчитано для {current_id} года для промыслового лова')
        # print(stock_da_prom.loc[current_id, :, :])

    # Считаем финальный результат (теперь координаты Year идеально совпадают)
    yearly_stock_net_with_ages_on_catch = weight_nauch * stock_da_nauch + weight_prom * stock_da_prom

    # сохраняем запасы без учета возрастов
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")
    output_nc_filename_net = f"{waterbody_name}_yearly_stock_net_with_ages_on_catch_3d.nc"
    output_nc_path_net = os.path.join(DATA_STOCK_DIR, output_nc_filename_net)
    yearly_stock_net_with_ages_on_catch.to_netcdf(output_nc_path_net, engine="netcdf4")

    return yearly_stock_net_with_ages_on_catch


def calc_yearly_stock_seine_out_ages_on_catch_3d(waterbody_name: str):
    fish_props = get_fish_prop(waterbody_name)
    square_by_years_dict = fish_props['площадь водоема']
    # переводим площадь в квадратные метры
    square_by_years_dict = {k: v * 1000000 for k, v in square_by_years_dict.items()}
    k_catchability_dict = fish_props['коэффициент уловистости невода']

    catch_seine_out_ages_3d = get_catch_seine_3d(waterbody_name)
    catch_seine_out_ages_3d_nauch = catch_seine_out_ages_3d.sel(CatchType='научный')
    catch_seine_out_ages_3d_prom = catch_seine_out_ages_3d.sel(CatchType='промысловый')

    # Сгруппируем массивы по Year по измерению 'Id'
    grouped_sum_nauch = (
        catch_seine_out_ages_3d_nauch.groupby(xr.DataArray(catch_seine_out_ages_3d_nauch.Year, dims="Id", name="Year")).sum(dim="Id")
    )
    grouped_count_nauch = (
        catch_seine_out_ages_3d_nauch.groupby(xr.DataArray(catch_seine_out_ages_3d_nauch.Year, dims='Id', name='Year')).count(dim='Id')
    )

    grouped_sum_prom = (
        catch_seine_out_ages_3d_prom.groupby(xr.DataArray(catch_seine_out_ages_3d_prom.Year, dims="Id", name="Year")).sum(dim="Id")
    )
    grouped_count_prom = (
        catch_seine_out_ages_3d_prom.groupby(xr.DataArray(catch_seine_out_ages_3d_prom.Year, dims='Id', name='Year')).count(dim='Id')
    )

    yearly_area_sum_nauch = catch_seine_out_ages_3d_nauch.coords['Area'].groupby('Year').sum(dim='Id')
    yearly_area_sum_prom = catch_seine_out_ages_3d_prom.coords['Area'].groupby('Year').sum(dim='Id')

    # Находим полный (объединенный) список всех уникальных годов из обоих массивов
    all_years = np.union1d(grouped_sum_nauch.Year.values, grouped_sum_prom.Year.values)

    # Принудительно приводим все массивы к общему списку годов, заполняя пропуски нулями
    grouped_sum_nauch = grouped_sum_nauch.reindex(Year=all_years, fill_value=0.0)
    grouped_count_nauch = grouped_count_nauch.reindex(Year=all_years, fill_value=0.0)

    grouped_sum_prom = grouped_sum_prom.reindex(Year=all_years, fill_value=0.0)
    grouped_count_prom = grouped_count_prom.reindex(Year=all_years, fill_value=0.0)

    # 3. Считаем сумму весов (теперь деление на ноль безопасно, так как xarray вернет NaN там, где сумма 0)
    total_count = grouped_count_nauch + grouped_count_prom

    weight_nauch = grouped_count_nauch / total_count
    weight_prom = grouped_count_prom / total_count

    # 4. Если в какой-то год не было вообще никаких ловов (сумма весов 0),
    # деление даст NaN. Заменяем эти NaN на 0, чтобы не испортить формулу
    weight_nauch = weight_nauch.fillna(0.0)
    weight_prom = weight_prom.fillna(0.0)

    # Фильтруем виды рыб
    fish_in_catchability = list(k_catchability_dict.keys())
    common_fish_list = list(set(fish_in_catchability))
    grouped_sum_nauch_filtered = grouped_sum_nauch.sel(FishType=common_fish_list)
    grouped_sum_prom_filtered = grouped_sum_prom.sel(FishType=common_fish_list)

    empty_matrix_nauch = np.zeros(
        (len(all_years), len(grouped_sum_nauch_filtered.FishType.values), len(grouped_sum_nauch_filtered.LessAge.values)),
        dtype=np.float64
    )

    # Упаковываем её в xr.DataArray и сразу привязываем подчиненные координаты
    stock_da_nauch = xr.DataArray(
        data=empty_matrix_nauch,
        coords={
            "Year": all_years,
            "FishType": grouped_sum_nauch_filtered.FishType.values,
            "LessAge": grouped_sum_nauch_filtered.LessAge.values,
        },
        dims=["Year", "FishType", "LessAge"],
    )

    stock_da_nauch = stock_da_nauch.assign_coords(
        age=("LessAge", grouped_sum_nauch_filtered.age.values)
    )

    for current_year in all_years:
        for current_fish in common_fish_list:
            for current_age in grouped_sum_nauch_filtered.LessAge.values:
                current_stock = grouped_sum_nauch_filtered.loc[current_year, current_fish, current_age].values * \
                                square_by_years_dict[current_year] / (k_catchability_dict[current_fish] * yearly_area_sum_nauch.loc[current_year].values * 10000)
                stock_da_nauch.loc[dict(Year=current_year, FishType=current_fish, LessAge=current_age)] = current_stock

        print(f'посчитано для {current_year} года для научного лова')
        # print(stock_da_nauch.loc[current_year, :, :])

    empty_matrix_prom = np.zeros(
        (len(all_years), len(grouped_sum_prom_filtered.FishType.values), len(grouped_sum_prom_filtered.LessAge.values)),
        dtype=np.float64
    )

    # Упаковываем её в xr.DataArray и сразу привязываем подчиненные координаты
    stock_da_prom = xr.DataArray(
        data=empty_matrix_prom,
        coords={
            "Year": all_years,
            "FishType": grouped_sum_prom_filtered.FishType.values,
            "LessAge": grouped_sum_prom_filtered.LessAge.values,
        },
        dims=["Year", "FishType", "LessAge"],
    )

    stock_da_prom = stock_da_prom.assign_coords(
        age=("LessAge", grouped_sum_prom_filtered.age.values)
    )

    for current_year in all_years:
        for current_fish in common_fish_list:
            for current_age in grouped_sum_prom_filtered.LessAge.values:
                current_stock = grouped_sum_prom_filtered.loc[current_year, current_fish, current_age].values * \
                                square_by_years_dict[current_year] / (k_catchability_dict[current_fish] * yearly_area_sum_prom.loc[current_year].values * 10000)
                stock_da_prom.loc[dict(Year=current_year, FishType=current_fish, LessAge=current_age)] = current_stock

        print(f'посчитано для {current_year} года для промыслового лова')
        # print(stock_da_prom.loc[current_id, :, :])


    # 5. Считаем финальный результат (теперь координаты Year идеально совпадают)
    yearly_stock_seine_out_ages = weight_nauch * stock_da_nauch + weight_prom * stock_da_prom

    # сохраняем запасы без учета возрастов
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")
    output_nc_filename_seine = f"{waterbody_name}_yearly_stock_seine_out_ages_on_catch_3d.nc"
    output_nc_path_seine = os.path.join(DATA_STOCK_DIR, output_nc_filename_seine)
    yearly_stock_seine_out_ages.to_netcdf(output_nc_path_seine, engine="netcdf4")

    return yearly_stock_seine_out_ages

def calc_yearly_stock_seine_with_ages_on_catch_3d(waterbody_name: str):
    fish_props = get_fish_prop(waterbody_name)
    square_by_years_dict = fish_props['площадь водоема']
    # переводим площадь в квадратные метры
    square_by_years_dict = {k: v * 1000000 for k, v in square_by_years_dict.items()}
    k_catchability = get_catchability_seine_3d(waterbody_name)

    catch_seine_with_ages_3d = get_catch_seine_3d(waterbody_name)
    catch_seine_with_ages_3d_nauch = catch_seine_with_ages_3d.sel(CatchType='научный')
    catch_seine_with_ages_3d_prom = catch_seine_with_ages_3d.sel(CatchType='промысловый')

    # Сгруппируем массивы по Year по измерению 'Id'
    grouped_sum_nauch = (
        catch_seine_with_ages_3d_nauch.groupby(xr.DataArray(catch_seine_with_ages_3d_nauch.Year, dims="Id", name="Year")).sum(dim="Id")
    )
    grouped_count_nauch = (
        catch_seine_with_ages_3d_nauch.groupby(xr.DataArray(catch_seine_with_ages_3d_nauch.Year, dims='Id', name='Year')).count(dim='Id')
    )

    grouped_sum_prom = (
        catch_seine_with_ages_3d_prom.groupby(xr.DataArray(catch_seine_with_ages_3d_prom.Year, dims="Id", name="Year")).sum(dim="Id")
    )
    grouped_count_prom = (
        catch_seine_with_ages_3d_prom.groupby(xr.DataArray(catch_seine_with_ages_3d_prom.Year, dims='Id', name='Year')).count(dim='Id')
    )

    yearly_area_sum_nauch = catch_seine_with_ages_3d_nauch.coords['Area'].groupby('Year').sum(dim='Id')
    yearly_area_sum_prom = catch_seine_with_ages_3d_prom.coords['Area'].groupby('Year').sum(dim='Id')

    # Находим полный (объединенный) список всех уникальных годов из обоих массивов
    all_years = np.union1d(grouped_sum_nauch.Year.values, grouped_sum_prom.Year.values)

    # Принудительно приводим все массивы к общему списку годов, заполняя пропуски нулями
    grouped_sum_nauch = grouped_sum_nauch.reindex(Year=all_years, fill_value=0.0)
    grouped_count_nauch = grouped_count_nauch.reindex(Year=all_years, fill_value=0.0)

    grouped_sum_prom = grouped_sum_prom.reindex(Year=all_years, fill_value=0.0)
    grouped_count_prom = grouped_count_prom.reindex(Year=all_years, fill_value=0.0)

    # 3. Считаем сумму весов (теперь деление на ноль безопасно, так как xarray вернет NaN там, где сумма 0)
    total_count = grouped_count_nauch + grouped_count_prom

    weight_nauch = grouped_count_nauch / total_count
    weight_prom = grouped_count_prom / total_count

    # 4. Если в какой-то год не было вообще никаких ловов (сумма весов 0),
    # деление даст NaN. Заменяем эти NaN на 0, чтобы не испортить формулу
    weight_nauch = weight_nauch.fillna(0.0)
    weight_prom = weight_prom.fillna(0.0)

    # Фильтруем виды рыб
    fish_in_catchability = list(k_catchability.FishType.values)
    common_fish_list = list(set(fish_in_catchability))
    grouped_sum_nauch_filtered = grouped_sum_nauch.sel(FishType=common_fish_list)
    grouped_sum_prom_filtered = grouped_sum_prom.sel(FishType=common_fish_list)

    empty_matrix_nauch = np.zeros(
        (len(all_years), len(grouped_sum_nauch_filtered.FishType.values), len(grouped_sum_nauch_filtered.LessAge.values)),
        dtype=np.float64
    )

    # Упаковываем её в xr.DataArray и сразу привязываем подчиненные координаты
    stock_da_nauch = xr.DataArray(
        data=empty_matrix_nauch,
        coords={
            "Year": all_years,
            "FishType": grouped_sum_nauch_filtered.FishType.values,
            "LessAge": grouped_sum_nauch_filtered.LessAge.values,
        },
        dims=["Year", "FishType", "LessAge"],
    )

    stock_da_nauch = stock_da_nauch.assign_coords(
        age=("LessAge", grouped_sum_nauch_filtered.age.values)
    )

    for current_year in all_years:
        for current_fish in common_fish_list:
            for current_age in grouped_sum_nauch_filtered.LessAge.values:
                catchability = k_catchability.loc[current_year, current_fish, current_age].values
                if catchability == 0:
                    current_stock = 0
                else:
                    current_stock = grouped_sum_nauch_filtered.loc[current_year, current_fish, current_age].values * \
                                square_by_years_dict[current_year] / (catchability *
                                yearly_area_sum_nauch.loc[current_year].values * 10000)
                stock_da_nauch.loc[dict(Year=current_year, FishType=current_fish, LessAge=current_age)] = current_stock

        print(f'посчитано для {current_year} года для научного лова')
        # print(stock_da_nauch.loc[current_year, :, :])

    empty_matrix_prom = np.zeros(
        (len(all_years), len(grouped_sum_prom_filtered.FishType.values), len(grouped_sum_prom_filtered.LessAge.values)),
        dtype=np.float64
    )

    # Упаковываем её в xr.DataArray и сразу привязываем подчиненные координаты
    stock_da_prom = xr.DataArray(
        data=empty_matrix_prom,
        coords={
            "Year": all_years,
            "FishType": grouped_sum_prom_filtered.FishType.values,
            "LessAge": grouped_sum_prom_filtered.LessAge.values,
        },
        dims=["Year", "FishType", "LessAge"],
    )

    stock_da_prom = stock_da_prom.assign_coords(
        age=("LessAge", grouped_sum_prom_filtered.age.values)
    )

    for current_year in all_years:
        for current_fish in common_fish_list:
            for current_age in grouped_sum_prom_filtered.LessAge.values:
                catchability = k_catchability.loc[current_year, current_fish, current_age].values
                if catchability == 0:
                    current_stock = 0
                else:
                    current_stock = grouped_sum_prom_filtered.loc[current_year, current_fish, current_age].values * \
                                square_by_years_dict[current_year] / (catchability *
                                yearly_area_sum_prom.loc[current_year].values * 10000)
                stock_da_prom.loc[dict(Year=current_year, FishType=current_fish, LessAge=current_age)] = current_stock

        print(f'посчитано для {current_year} года для промыслового лова')
        # print(stock_da_prom.loc[current_id, :, :])


    # Считаем финальный результат (теперь координаты Year идеально совпадают)
    yearly_stock_seine_with_ages = weight_nauch * stock_da_nauch + weight_prom * stock_da_prom

    # сохраняем запасы без учета возрастов
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")
    output_nc_filename_seine = f"{waterbody_name}_yearly_stock_seine_with_ages_on_catch_3d.nc"
    output_nc_path_seine = os.path.join(DATA_STOCK_DIR, output_nc_filename_seine)
    yearly_stock_seine_with_ages.to_netcdf(output_nc_path_seine, engine="netcdf4")

    return yearly_stock_seine_with_ages


if __name__ == '__main__':
    yearly_stock_net_out_ages_3d = calc_yearly_stock_net_out_ages_on_catch_3d('zhaysan')
    yearly_stock_net_with_ages_3d = calc_yearly_stock_net_with_ages_on_catch_3d('zhaysan')
    yearly_stock_seine_out_ages_3d = calc_yearly_stock_seine_out_ages_on_catch_3d('zhaysan')
    yearly_stock_seine_with_ages_3d = calc_yearly_stock_seine_with_ages_on_catch_3d('zhaysan')

    print(yearly_stock_net_out_ages_3d.sel(FishType='лещ').to_pandas())
    print('закончил сеть без учета возрастов', type(yearly_stock_net_out_ages_3d))
    print(yearly_stock_net_with_ages_3d.sel(FishType='лещ').to_pandas())
    print('закончил сеть с учетом возрастов', type(yearly_stock_net_with_ages_3d))
    print(yearly_stock_seine_out_ages_3d.sel(FishType='лещ').to_pandas())
    print('закончил невод без учета возрастов')
    print(yearly_stock_seine_with_ages_3d.sel(FishType='лещ').to_pandas())
    print('закончил сеть с учетом возрастов')