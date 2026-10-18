import os
import sys
import xarray as xr

def get_stock_bayes_net_3d(waterbody_name: str, with_ages: bool, flag: str = ''):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема
    if with_ages:
        file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_bayes_onegear_net_with_ages_3d_{flag}.nc")
    else:
        file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_bayes_onegear_net_out_ages_3d_{flag}.nc")

    if not file_path:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    result_ds = xr.open_dataset(file_path)
    # stock_net_3d = result_ds['stock']

    return result_ds


def get_stock_bayes_seine_3d(waterbody_name: str, with_ages: bool, flag: str = ''):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема
    if with_ages:
        file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_bayes_onegear_seine_with_ages_3d_{flag}.nc")
    else:
        file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_bayes_onegear_seine_out_ages_3d_{flag}.nc")

    if not file_path:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    result_ds = xr.open_dataset(file_path)
    # stock_seine_3d = result_ds['stock']

    return result_ds


def get_stock_bayes_twogear(waterbody_name: str, with_ages: bool, flag: str = ''):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема
    if with_ages:
        file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_bayes_twogear_2_with_ages_3d_{flag}.nc")
    else:
        file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_bayes_twogear_2_out_ages_3d_{flag}.nc")

    if not file_path:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    result_ds = xr.open_dataset(file_path)
    # stock_twogear_3d = result_ds['stock']

    return result_ds



if __name__ == '__main__':
    stock_net_out_ages_3d = get_stock_bayes_net_3d('zhaysan', False)
    print('stock_net_out_ages_3d shape and dims = ', stock_net_out_ages_3d.shape, stock_net_out_ages_3d.dims)
    print()
    print('stock_net_out_ages_3d = \n', stock_net_out_ages_3d.sum(dim='age').to_pandas())

    stock_seine_out_ages_3d = get_stock_bayes_seine_3d('zhaysan', False)
    print('stock_seine_out_ages_3d shape and dims = ', stock_seine_out_ages_3d.shape, stock_seine_out_ages_3d.dims)
    print()
    print('stock_seine_out_ages_3d = \n', stock_seine_out_ages_3d.sum(dim='age').to_pandas())

    stock_twogear_2_out_ages = get_stock_bayes_twogear('zhaysan', False)
    print('stock_twogear_2_out_ages_3d shape and dims = ', stock_twogear_2_out_ages.shape, stock_twogear_2_out_ages.dims)
    print()
    print('stock_twogear_2_out_ages_3d = \n', stock_twogear_2_out_ages.sum(dim='age').to_pandas())

    differ_stock_3d = stock_seine_out_ages_3d - stock_net_out_ages_3d
    print('разность запасов ')
    # print(differ_stock_3d)

    stock_net_out_ages_2d = stock_net_out_ages_3d.sum(dim='age')
    stock_seine_out_ages_2d = stock_seine_out_ages_3d.sum(dim='age')
    print('stock_net_out_ages_2d = ', stock_seine_out_ages_2d.to_pandas())
    print('stock_seine_out_ages_2d = ', stock_seine_out_ages_2d.to_pandas())
    print('разность сумм = ')
    print((stock_seine_out_ages_2d / stock_net_out_ages_2d).to_pandas())


