import os
import xarray as xr
import numpy as np
from get_stock_3d import get_stock_net_out_ages_3d, get_stock_net_with_ages_3d, get_stock_seine_out_ages_3d, get_stock_seine_with_ages_3d

def calc_yearly_stock_net_out_ages_on_stock_3d(waterbody_name: str):
    stock_net_out_ages_3d = get_stock_net_out_ages_3d(waterbody_name)
    stock_net_out_ages_3d_nauch = stock_net_out_ages_3d.sel(CatchType='научный')
    stock_net_out_ages_3d_prom = stock_net_out_ages_3d.sel(CatchType='промысловый')

    # Сгруппируем массивы по Year по измерению 'Id'
    grouped_means_nauch = (
        stock_net_out_ages_3d_nauch.groupby(xr.DataArray(stock_net_out_ages_3d_nauch.Year, dims="Id", name="Year")).mean(dim="Id")
    )
    grouped_count_nauch = (
        stock_net_out_ages_3d_nauch.groupby(xr.DataArray(stock_net_out_ages_3d_nauch.Year, dims='Id', name='Year')).count(dim='Id')
    )

    grouped_means_prom = (
        stock_net_out_ages_3d_prom.groupby(xr.DataArray(stock_net_out_ages_3d_prom.Year, dims="Id", name="Year")).mean(dim="Id")
    )
    grouped_count_prom = (
        stock_net_out_ages_3d_prom.groupby(xr.DataArray(stock_net_out_ages_3d_prom.Year, dims='Id', name='Year')).count(dim='Id')
    )

    # Находим полный (объединенный) список всех уникальных годов из обоих массивов
    all_years = np.union1d(grouped_means_nauch.Year.values, grouped_means_prom.Year.values)

    # Принудительно приводим все массивы к общему списку годов, заполняя пропуски нулями
    grouped_means_nauch = grouped_means_nauch.reindex(Year=all_years, fill_value=0.0)
    grouped_count_nauch = grouped_count_nauch.reindex(Year=all_years, fill_value=0.0)

    grouped_means_prom = grouped_means_prom.reindex(Year=all_years, fill_value=0.0)
    grouped_count_prom = grouped_count_prom.reindex(Year=all_years, fill_value=0.0)

    # Считаем сумму весов (теперь деление на ноль безопасно, так как xarray вернет NaN там, где сумма 0)
    total_count = grouped_count_nauch + grouped_count_prom

    weight_nauch = grouped_count_nauch / total_count
    weight_prom = grouped_count_prom / total_count

    # Если в какой-то год не было вообще никаких ловов (сумма весов 0),
    # деление даст NaN. Заменяем эти NaN на 0, чтобы не испортить формулу
    weight_nauch = weight_nauch.fillna(0.0)
    weight_prom = weight_prom.fillna(0.0)

    # Считаем финальный результат (теперь координаты Year идеально совпадают)
    yearly_stock_net_out_ages = weight_nauch * grouped_means_nauch + weight_prom * grouped_means_prom

    # сохраняем запасы без учета возрастов
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")
    output_nc_filename_net = f"{waterbody_name}_yearly_stock_net_out_ages_on_stock_3d.nc"
    output_nc_path_net = os.path.join(DATA_STOCK_DIR, output_nc_filename_net)
    yearly_stock_net_out_ages.to_netcdf(output_nc_path_net, engine="netcdf4")

    return yearly_stock_net_out_ages

def calc_yearly_stock_net_with_ages_on_stock_3d(waterbody_name: str):
    stock_net_with_ages_3d = get_stock_net_with_ages_3d(waterbody_name)
    stock_net_with_ages_3d_nauch = stock_net_with_ages_3d.sel(CatchType='научный')
    stock_net_with_ages_3d_prom = stock_net_with_ages_3d.sel(CatchType='промысловый')

    # Сгруппируем массивы по Year по измерению 'Id'
    grouped_means_nauch = (
        stock_net_with_ages_3d_nauch.groupby(xr.DataArray(stock_net_with_ages_3d_nauch.Year, dims="Id", name="Year")).mean(dim="Id")
    )
    grouped_count_nauch = (
        stock_net_with_ages_3d_nauch.groupby(xr.DataArray(stock_net_with_ages_3d_nauch.Year, dims='Id', name='Year')).count(dim='Id')
    )

    grouped_means_prom = (
        stock_net_with_ages_3d_prom.groupby(xr.DataArray(stock_net_with_ages_3d_prom.Year, dims="Id", name="Year")).mean(dim="Id")
    )
    grouped_count_prom = (
        stock_net_with_ages_3d_prom.groupby(xr.DataArray(stock_net_with_ages_3d_prom.Year, dims='Id', name='Year')).count(dim='Id')
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

    # 5. Считаем финальный результат (теперь координаты Year идеально совпадают)
    yearly_stock_net_with_ages = weight_nauch * grouped_means_nauch + weight_prom * grouped_means_prom

    # сохраняем запасы без учета возрастов
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")
    output_nc_filename_net = f"{waterbody_name}_yearly_stock_net_with_ages_on_stock_3d.nc"
    output_nc_path_net = os.path.join(DATA_STOCK_DIR, output_nc_filename_net)
    yearly_stock_net_with_ages.to_netcdf(output_nc_path_net, engine="netcdf4")

    return yearly_stock_net_with_ages


def calc_yearly_stock_seine_out_ages_on_stock_3d(waterbody_name: str):
    stock_seine_out_ages_3d = get_stock_seine_out_ages_3d(waterbody_name)
    stock_seine_out_ages_3d_nauch = stock_seine_out_ages_3d.sel(CatchType='научный')
    stock_seine_out_ages_3d_prom = stock_seine_out_ages_3d.sel(CatchType='промысловый')

    # Сгруппируем массивы по Year по измерению 'Id'
    grouped_means_nauch = (
        stock_seine_out_ages_3d_nauch.groupby(xr.DataArray(stock_seine_out_ages_3d_nauch.Year, dims="Id", name="Year")).mean(dim="Id")
    )
    grouped_count_nauch = (
        stock_seine_out_ages_3d_nauch.groupby(xr.DataArray(stock_seine_out_ages_3d_nauch.Year, dims='Id', name='Year')).count(dim='Id')
    )

    grouped_means_prom = (
        stock_seine_out_ages_3d_prom.groupby(xr.DataArray(stock_seine_out_ages_3d_prom.Year, dims="Id", name="Year")).mean(dim="Id")
    )
    grouped_count_prom = (
        stock_seine_out_ages_3d_prom.groupby(xr.DataArray(stock_seine_out_ages_3d_prom.Year, dims='Id', name='Year')).count(dim='Id')
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

    # 5. Считаем финальный результат (теперь координаты Year идеально совпадают)
    yearly_stock_seine_out_ages = weight_nauch * grouped_means_nauch + weight_prom * grouped_means_prom

    # сохраняем запасы без учета возрастов
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")
    output_nc_filename_seine = f"{waterbody_name}_yearly_stock_seine_out_ages_on_stock_3d.nc"
    output_nc_path_seine = os.path.join(DATA_STOCK_DIR, output_nc_filename_seine)
    yearly_stock_seine_out_ages.to_netcdf(output_nc_path_seine, engine="netcdf4")

    return yearly_stock_seine_out_ages

def calc_yearly_stock_seine_with_ages_on_stock_3d(waterbody_name: str):
    stock_seine_with_ages_3d = get_stock_seine_with_ages_3d(waterbody_name)
    stock_seine_with_ages_3d_nauch = stock_seine_with_ages_3d.sel(CatchType='научный')
    stock_seine_with_ages_3d_prom = stock_seine_with_ages_3d.sel(CatchType='промысловый')

    # Сгруппируем массивы по Year по измерению 'Id'
    grouped_means_nauch = (
        stock_seine_with_ages_3d_nauch.groupby(xr.DataArray(stock_seine_with_ages_3d_nauch.Year, dims="Id", name="Year")).mean(dim="Id")
    )
    grouped_count_nauch = (
        stock_seine_with_ages_3d_nauch.groupby(xr.DataArray(stock_seine_with_ages_3d_nauch.Year, dims='Id', name='Year')).count(dim='Id')
    )

    grouped_means_prom = (
        stock_seine_with_ages_3d_prom.groupby(xr.DataArray(stock_seine_with_ages_3d_prom.Year, dims="Id", name="Year")).mean(dim="Id")
    )
    grouped_count_prom = (
        stock_seine_with_ages_3d_prom.groupby(xr.DataArray(stock_seine_with_ages_3d_prom.Year, dims='Id', name='Year')).count(dim='Id')
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

    # 5. Считаем финальный результат (теперь координаты Year идеально совпадают)
    yearly_stock_seine_with_ages = weight_nauch * grouped_means_nauch + weight_prom * grouped_means_prom

    # сохраняем запасы без учета возрастов
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")
    output_nc_filename_seine = f"{waterbody_name}_yearly_stock_seine_with_ages_on_stock_3d.nc"
    output_nc_path_seine = os.path.join(DATA_STOCK_DIR, output_nc_filename_seine)
    yearly_stock_seine_with_ages.to_netcdf(output_nc_path_seine, engine="netcdf4")

    return yearly_stock_seine_with_ages


if __name__ == '__main__':
    yearly_stock_net_out_ages_3d = calc_yearly_stock_net_out_ages_on_stock_3d('zhaysan')
    yearly_stock_net_with_ages_3d = calc_yearly_stock_net_with_ages_on_stock_3d('zhaysan')
    yearly_stock_seine_out_ages_3d = calc_yearly_stock_seine_out_ages_on_stock_3d('zhaysan')
    yearly_stock_seine_with_ages_3d = calc_yearly_stock_seine_with_ages_on_stock_3d('zhaysan')

    print(yearly_stock_net_out_ages_3d.sel(FishType='лещ').to_pandas())
    print('закончил сеть без учета возрастов')
    print(yearly_stock_net_with_ages_3d.sel(FishType='лещ').to_pandas())
    print('закончил сеть с учетом возрастов')
    print(yearly_stock_seine_out_ages_3d.sel(FishType='лещ').to_pandas())
    print('закончил невод без учета возрастов')
    print(yearly_stock_seine_with_ages_3d.sel(FishType='лещ').to_pandas())
    print('закончил сеть с учетом возрастов')