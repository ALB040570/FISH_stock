import os
import sys
import xarray as xr

# Чтение данных о ежегодном запасе по сетям без учета возрастов, рассчитанных на основе запасов
def get_yearly_stock_net_out_ages_on_stock_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_yearly_stock_net_out_ages_on_stock_3d.nc")

    if not file_path:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    yearly_stock_net_out_ages_3d = xr.open_dataarray(file_path)
    return yearly_stock_net_out_ages_3d

# Чтение данных о ежегодном запасе по сетям с учетом возрастов, рассчитанных на основе запасов
def get_yearly_stock_net_with_ages_on_stock_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_yearly_stock_net_with_ages_on_stock_3d.nc")

    if not file_path:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    yearly_stock_net_with_ages_3d = xr.open_dataarray(file_path)
    return yearly_stock_net_with_ages_3d


# Чтение данных о ежегодных запсах по неводамм без учета возрастов, рассчитанных на основе запасов
def get_yearly_stock_seine_out_ages_on_stock_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема (например: data_stock/balkhash_catch_seine_3d.n)
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_yearly_stock_seine_out_ages_on_stock_3d.nc")

    if not file_path:
        print(f"[!] Файл для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    yearly_stock_seine_out_ages_3d = xr.open_dataarray(file_path)
    return yearly_stock_seine_out_ages_3d


# Чтение данных о ежегодных запсах по неводамм без учета возрастов, рассчитанных на основе запасов
def get_yearly_stock_seine_with_ages_on_stock_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема (например: data_stock/balkhash_catch_seine_3d.n)
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_yearly_stock_seine_with_ages_on_stock_3d.nc")

    if not file_path:
        print(f"[!] Файл для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    yearly_stock_seine_with_ages_3d = xr.open_dataarray(file_path)
    return yearly_stock_seine_with_ages_3d

# Чтение данных о ежегодном запасе по сетям без учета возрастов, рассчитанных на основе выловов
def get_yearly_stock_net_out_ages_on_catch_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_yearly_stock_net_out_ages_on_catch_3d.nc")

    if not file_path:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    yearly_stock_net_out_ages_3d = xr.open_dataarray(file_path)
    return yearly_stock_net_out_ages_3d

# Чтение данных о ежегодном запасе по сетям с учетом возрастов, рассчитанных на основе выловов
def get_yearly_stock_net_with_ages_on_catch_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_yearly_stock_net_with_ages_on_catch_3d.nc")

    if not file_path:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    yearly_stock_net_with_ages_3d = xr.open_dataarray(file_path)
    return yearly_stock_net_with_ages_3d


# Чтение данных о ежегодных запсах по неводамм без учета возрастов, рассчитанных на основе выловов
def get_yearly_stock_seine_out_ages_on_catch_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема (например: data_stock/balkhash_catch_seine_3d.n)
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_yearly_stock_seine_out_ages_on_catch_3d.nc")

    if not file_path:
        print(f"[!] Файл для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    yearly_stock_seine_out_ages_3d = xr.open_dataarray(file_path)
    return yearly_stock_seine_out_ages_3d


# Чтение данных о ежегодных запсах по неводамм без учета возрастов, рассчитанных на основе выловов
def get_yearly_stock_seine_with_ages_on_catch_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема (например: data_stock/balkhash_catch_seine_3d.n)
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_yearly_stock_seine_with_ages_on_catch_3d.nc")

    if not file_path:
        print(f"[!] Файл для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    yearly_stock_seine_with_ages_3d = xr.open_dataarray(file_path)
    return yearly_stock_seine_with_ages_3d




# --- ТЕСТОВЫЙ ЗАПУСК ВНУТРИ МОДУЛЯ ---
if __name__ == "__main__":
    zhaysan_yearly_stock_net_out_ages_3d = get_yearly_stock_net_out_ages_on_stock_3d("zhaysan")
    print(zhaysan_yearly_stock_net_out_ages_3d.shape, zhaysan_yearly_stock_net_out_ages_3d.dims)
    print(zhaysan_yearly_stock_net_out_ages_3d.sum('LessAge').to_pandas())

    zhaysan_yearly_stock_net_with_ages_3d = get_yearly_stock_net_with_ages_on_stock_3d("zhaysan")
    print(zhaysan_yearly_stock_net_with_ages_3d.shape, zhaysan_yearly_stock_net_with_ages_3d.dims)
    print(zhaysan_yearly_stock_net_with_ages_3d.sum('LessAge').to_pandas())

    zhaysan_yearly_stock_seine_out_ages_3d = get_yearly_stock_seine_out_ages_on_stock_3d("zhaysan")
    print(zhaysan_yearly_stock_seine_out_ages_3d.shape, zhaysan_yearly_stock_seine_out_ages_3d.dims)
    print(zhaysan_yearly_stock_seine_out_ages_3d.sum('LessAge').to_pandas())

    zhaysan_yearly_stock_seine_with_ages_3d = get_yearly_stock_seine_with_ages_on_stock_3d("zhaysan")
    print(zhaysan_yearly_stock_seine_with_ages_3d.shape, zhaysan_yearly_stock_seine_with_ages_3d.dims)
    print(zhaysan_yearly_stock_seine_with_ages_3d.sum('LessAge').to_pandas())

    zhaysan_yearly_stock_net_out_ages_3d = get_yearly_stock_net_out_ages_on_catch_3d("zhaysan")
    print(zhaysan_yearly_stock_net_out_ages_3d.shape, zhaysan_yearly_stock_net_out_ages_3d.dims)
    print(zhaysan_yearly_stock_net_out_ages_3d.sum('LessAge').to_pandas())

    zhaysan_yearly_stock_net_with_ages_3d = get_yearly_stock_net_with_ages_on_catch_3d("zhaysan")
    print(zhaysan_yearly_stock_net_with_ages_3d.shape, zhaysan_yearly_stock_net_with_ages_3d.dims)
    print(zhaysan_yearly_stock_net_with_ages_3d.sum('LessAge').to_pandas())

    zhaysan_yearly_stock_seine_out_ages_3d = get_yearly_stock_seine_out_ages_on_catch_3d("zhaysan")
    print(zhaysan_yearly_stock_seine_out_ages_3d.shape, zhaysan_yearly_stock_seine_out_ages_3d.dims)
    print(zhaysan_yearly_stock_seine_out_ages_3d.sum('LessAge').to_pandas())

    zhaysan_yearly_stock_seine_with_ages_3d = get_yearly_stock_seine_with_ages_on_catch_3d("zhaysan")
    print(zhaysan_yearly_stock_seine_with_ages_3d.shape, zhaysan_yearly_stock_seine_with_ages_3d.dims)
    print(zhaysan_yearly_stock_seine_with_ages_3d.sum('LessAge').to_pandas())

