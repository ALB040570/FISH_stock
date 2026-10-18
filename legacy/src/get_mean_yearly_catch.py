import os
import xarray as xr
from get_catch_3d import get_catch_net_3d, get_catch_seine_3d


def save_catch_yealy_mean(waterbody_name: str):
    catch_net_3d = get_catch_net_3d(waterbody_name)
    catch_seine_3d = get_catch_seine_3d(waterbody_name)

    catch_mean_yearly_net = catch_net_3d.groupby(xr.DataArray(catch_net_3d.Year, dims='Id', name='Year')).mean(dim='Id')
    catch_mean_yearly_seine = catch_seine_3d.groupby(xr.DataArray(catch_seine_3d.Year, dims='Id', name='Year')).mean(dim='Id')

    # сохраняем запасы без учета возрастов
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")
    output_nc_filename_net = f"{waterbody_name}_mean_yearly_catch_net_3d.nc"
    output_nc_path_net = os.path.join(DATA_STOCK_DIR, output_nc_filename_net)
    catch_mean_yearly_net.to_netcdf(output_nc_path_net, engine="netcdf4")

    output_nc_filename_seine = f"{waterbody_name}_mean_yearly_catch_seine_3d.nc"
    output_nc_path_seine = os.path.join(DATA_STOCK_DIR, output_nc_filename_seine)
    catch_mean_yearly_seine.to_netcdf(output_nc_path_seine, engine="netcdf4")


    print(catch_mean_yearly_net.shape, catch_mean_yearly_net.dims)
    print(catch_mean_yearly_seine.shape, catch_mean_yearly_seine.dims)
    print('сеть = ', catch_mean_yearly_net.sel({'FishType': ['лещ', 'судак', 'окунь', 'плотва']}).sum('LessAge').to_pandas())
    print('невод = ', catch_mean_yearly_seine.sel({'FishType': ['лещ', 'судак', 'окунь', 'плотва']}).sum('LessAge').to_pandas())


if __name__ == '__main__':
    save_catch_yealy_mean('zhaysan')