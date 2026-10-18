import os
import sys
import xarray as xr
import importlib


# Чтение данных о запасе по сетям без учета возрастов
def get_stock_npc_3d(waterbody_name):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Ищем файлы строго для конкретного водоема
    file_path = os.path.join(DATA_STOCK_DIR, f"{waterbody_name}_stock_npc_3d.nc")

    if not file_path:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_stock не найден.")
        return

    stock_npc_3d = xr.open_dataarray(file_path)
    return stock_npc_3d


# возвращает двумерный массив ПДУ в граммах
def get_pdu_tons_2d(waterbody_name: str):
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)

    DATA_CATCH_DIR = os.path.join(PROJECT_ROOT, "data_catch")

    # Ищем файлы строго для конкретного водоема (например: data_catch/balkhash_catch_*.py)
    file_path = os.path.join(DATA_CATCH_DIR, f"{waterbody_name}_npc_assessment.py")

    if not file_path:
        print(f"[!] Файлы для водоема '{waterbody_name}' в папке data_catch не найдены.")
        return df_stock_npc

    file_name_tuple = os.path.splitext(os.path.basename(file_path))
    file_name = file_name_tuple[0]  # Чистая строка из кортежа splitext

    try:
        imported_module = importlib.import_module(f"data_catch.{file_name}")
        df_pdu_npc = getattr(imported_module, 'data_pdu_npc').copy()
        df_pdu_npc = df_pdu_npc.set_index('Id')
    except Exception as e:
        print(f"[ошибка: ] {e}")

    # Конвертируем в 2D DataArray
    da_pdu = xr.DataArray(
        df_pdu_npc,
        dims=["Year", "FishType"],
        coords={
            "Year": df_pdu_npc.index.values,
            "FishType": df_pdu_npc.columns,
        }
    )

    return da_pdu



if __name__ == '__main__':
    pdu_gramm = get_pdu_tons_2d('zhaysan')

    # print(pdu_gramm.shape, pdu_gramm.dims)
    # print(pdu_gramm.to_pandas())
