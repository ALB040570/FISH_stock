import os
import sys
import xarray as xr

# Чтение данных о запасе по сетям без учета возрастов
def get_stock_net_out_ages_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_stock_net_out_ages_3d.nc")

    if not file_path:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    stock_net_out_ages_3d = xr.open_dataarray(file_path)
    return stock_net_out_ages_3d

# Чтение данных о запасе по сетям с учетом возрастов
def get_stock_net_with_ages_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_stock_net_with_ages_3d.nc")

    if not file_path:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    stock_net_with_ages_3d = xr.open_dataarray(file_path)
    return stock_net_with_ages_3d


# Чтение данных о запсах по неводамм без учета возрастов
def get_stock_seine_out_ages_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема (например: data_stock/balkhash_catch_seine_3d.n)
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_stock_seine_out_ages_3d.nc")

    if not file_path:
        print(f"[!] Файл для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    stock_seine_out_ages_3d = xr.open_dataarray(file_path)
    return stock_seine_out_ages_3d

# Чтение данных о запсах по неводамм без учета возрастов
def get_stock_seine_with_ages_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема (например: data_stock/balkhash_catch_seine_3d.n)
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_stock_seine_with_ages_3d.nc")

    if not file_path:
        print(f"[!] Файл для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    stock_seine_with_ages_3d = xr.open_dataarray(file_path)
    return stock_seine_with_ages_3d



# --- ТЕСТОВЫЙ ЗАПУСК ВНУТРИ МОДУЛЯ ---
if __name__ == "__main__":
    zhaysan_stock_net_out_ages_3d = get_stock_net_out_ages_3d("zhaysan")
    print(zhaysan_stock_net_out_ages_3d.shape, zhaysan_stock_net_out_ages_3d.dims)
    print(zhaysan_stock_net_out_ages_3d.sum('LessAge').to_pandas())

    zhaysan_stock_net_with_ages_3d = get_stock_net_with_ages_3d("zhaysan")
    print(zhaysan_stock_net_with_ages_3d.shape, zhaysan_stock_net_with_ages_3d.dims)
    print(zhaysan_stock_net_with_ages_3d.sum('LessAge').to_pandas())

    zhaysan_stock_seine_out_ages_3d = get_stock_seine_out_ages_3d("zhaysan")
    print(zhaysan_stock_seine_out_ages_3d.shape, zhaysan_stock_seine_out_ages_3d.dims)
    print(zhaysan_stock_seine_out_ages_3d.sum('LessAge').to_pandas())

    zhaysan_stock_seine_with_ages_3d = get_stock_seine_with_ages_3d("zhaysan")
    print(zhaysan_stock_seine_with_ages_3d.shape, zhaysan_stock_seine_with_ages_3d.dims)
    print(zhaysan_stock_seine_with_ages_3d.sum('LessAge').to_pandas())

