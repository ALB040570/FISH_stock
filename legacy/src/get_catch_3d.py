import os
import sys
import xarray as xr

# Чтение данных об уловах сетью
def get_catch_net_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема (например: data_stock/balkhash_catch_net_3d.n)
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_catch_net_3d.nc")

    if not file_path:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    catch_net_3d = xr.open_dataarray(file_path)
    return catch_net_3d

# Чтение данных об уловах неводом
def get_catch_seine_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема (например: data_stock/balkhash_catch_seine_3d.n)
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_catch_seine_3d.nc")

    if not file_path:
        print(f"[!] Файл для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    catch_seine_3d = xr.open_dataarray(file_path)
    return catch_seine_3d


# --- ТЕСТОВЫЙ ЗАПУСК ВНУТРИ МОДУЛЯ ---
if __name__ == "__main__":
    zhaysan_catch_net_3d = get_catch_net_3d("zhaysan")
    print(zhaysan_catch_net_3d.shape, zhaysan_catch_net_3d.dims)
    print(zhaysan_catch_net_3d.sum('LessAge').to_pandas())

    zhaysan_catch_seine_3d = get_catch_seine_3d("zhaysan")
    print(zhaysan_catch_seine_3d.shape, zhaysan_catch_seine_3d.dims)
    print(zhaysan_catch_seine_3d.sum('LessAge').to_pandas())
    print(zhaysan_catch_seine_3d)
