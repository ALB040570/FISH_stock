import os, sys
import importlib
import xarray as xr


def get_fish_prop(waterbody_name: str):
    # 1. Настройка путей проекта
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_CATCH_DIR = os.path.join(PROJECT_ROOT, "data_catch")
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    # Добавляем корень проекта в пути, чтобы Python видел папку data_catch как пакет
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Формируем ИМЯ МОДУЛЯ для импорта (через точку, БЕЗ .py)
    module_name = f"data_catch.{waterbody_name}_fish_prop"

    # Для отладки соберем и физический путь, чтобы проверить существование файла
    file_path = os.path.join(DATA_CATCH_DIR, f"{waterbody_name}_fish_prop.py")

    # Динамический импорт модуля параметров
    try:
        prop_module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        raise FileNotFoundError(
            f"Не удалось импортировать {module_name}. "
            f"Проверьте наличие файла {file_path}. Ошибка: {e}"
        )

    # Безопасное извлечение переменных
    square_by_years_dict = getattr(prop_module, 'square_by_years')
    time_net_hour_dict = getattr(prop_module, 'time_net_hour')
    v_cr_dict = getattr(prop_module, 'v_cr_dict')
    k_catchability_net_dict = getattr(prop_module, 'k_catchability_1')
    k_catchability_seine_dict = getattr(prop_module, 'k_catchability_2')
    net_length_dict = getattr(prop_module, 'net_length')
    m0_dict = getattr(prop_module, 'm0_dict')
    m1_dict = getattr(prop_module, 'm1_dict')
    m2_dict = getattr(prop_module, 'm2_dict')
    fish_types_dict = getattr(prop_module, 'fish_list_dict')
    fish_is_predator_dict = getattr(prop_module, 'fish_is_predator_dict')
    fecundity_dict = getattr(prop_module, 'fecundity_dict')
    fish_density_dict = getattr(prop_module, 'fish_density_dict')

    fish_props = {
        'площадь водоема': square_by_years_dict,
        'время стоянки сети': time_net_hour_dict,
        'скорость рыбы': v_cr_dict,
        'коэффициент уловистости сети': k_catchability_net_dict,
        'коэффициент уловистости невода': k_catchability_seine_dict,
        'длина сети': net_length_dict,
        'возраст половой зрелости': m0_dict,
        'максимальный возраст': m1_dict,
        'возраст для хищников': m2_dict,
        'виды рыб': fish_types_dict,
        'признак хищника': fish_is_predator_dict,
        'количество икринок': fecundity_dict,
        'максимальное количество мальков': fish_density_dict
    }

    return fish_props

# возвращает трехмерный массив средних весов рыб с измерениями Year, FishType, LessAge
def get_fish_weight_3d(waterbody_name: str, fish_types: list):
    # 1. Настройка путей проекта
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    DATA_CATCH_DIR = os.path.join(PROJECT_ROOT, "data_catch")
    DATA_STOCK_DIR = os.path.join(PROJECT_ROOT, "data_stock")

    # Добавляем корень проекта в пути, чтобы Python видел папку data_catch как пакет
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Формируем ИМЯ МОДУЛЯ для импорта (через точку, БЕЗ .py)
    module_name = f"data_catch.{waterbody_name}_fish_prop"

    # Для отладки соберем и физический путь, чтобы проверить существование файла
    file_path = os.path.join(DATA_CATCH_DIR, f"{waterbody_name}_fish_prop.py")

    # Динамический импорт модуля параметров
    try:
        prop_module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        raise FileNotFoundError(
            f"Не удалось импортировать {module_name}. "
            f"Проверьте наличие файла {file_path}. Ошибка: {e}"
        )

    fish_list_dict = getattr(prop_module, 'fish_list_dict')
    fish_weight_array = []
    for fish in fish_types:
        if fish in fish_list_dict:
            var_name = fish_list_dict[fish]
            if hasattr(prop_module, var_name):
                df = getattr(prop_module, var_name)
                df = df.set_index(['LessAge', 'age'])
                less_age_labels = df.index.get_level_values('LessAge').values
                age_numbers = df.index.get_level_values('age').values
                # Собираем двумерный xarray.DataArray из DataFrame
                fish_da = xr.DataArray(
                    data=df.values,
                    coords={
                        "LessAge": less_age_labels,  # Строки датафрейма -> Возрасты
                        "Year": df.columns.values,  # Столбцы датафрейма -> Годы
                        "age": ("LessAge", age_numbers)
                    },
                    dims=["LessAge", "Year"]
                )
                # Присваиваем координату FishType на русском языке,
                # чтобы массив идеально стыковался массивом уловов
                fish_da = fish_da.assign_coords(FishType=fish)
                fish_weight_array.append(fish_da)
                # print(f"Успешно загружен вес для: {fish} (переменная {var_name})")

                # print('рыба ', fish, fish_da.shape)
                # print('dataarray = ', fish_da)
                # print(fish_da.LessAge.values, fish_da.Year.values, fish_da.FishType.values)
                # print('datafraime = ', df)

            else:
                print(f"Предупреждение: Переменная '{var_name}' не найдена внутри файла {file_path}")
        else:
            print(f"Предупреждение: Рыба '{fish}' отсутствует в словаре сопоставления имен.")

    if not fish_weight_array:
        raise ValueError("Не удалось загрузить ни один массив весов. Проверьте список рыб и словарь сопоставления.")

    # Объединяем плоские таблицы по координате FishType в единый куб
    # weights_3d = xr.concat(fish_weight_array, dim="FishType", join='outer')
    weights_3d = xr.concat(
        fish_weight_array,
        dim="FishType",
        join='outer',
        coords='different',
        compat='no_conflicts',
        fill_value=0.0
    )

    # Из-за растяжения в координате 'age' появились NaN (для отсутствующих возрастов).
    # Мы генерируем правильные числа заново, вытаскивая их прямо из итоговых текстовых строк 'LessAge'
    # Например, если строка 'less_14', код распарсит её и запишет число 14.0
    import numpy as np
    try:
        # Извлекаем числа из названий (работает, если формат строк везде типа 'less_12' или 'Age 12')
        final_ages = np.array([float(''.join(c for c in str(x) if c.isdigit() or c == '.')) for x in weights_3d.LessAge.values])
    except ValueError:
        # Если в строках нет чисел, создаем последовательность 2, 3, 4... по длине получившейся оси
        final_ages = np.arange(2, 2 + len(weights_3d.LessAge))

    # Перезаписываем координату age чистыми числами без NaN
    weights_3d = weights_3d.assign_coords(age=("LessAge", final_ages))

    # Выстраиваем оси в стандартном порядке: Год, Вид рыбы, Возраст
    weights_3d = weights_3d.transpose("Year", "FishType", "LessAge")

    return weights_3d.sortby('age')




if __name__ == '__main__':
    fish_props = get_fish_prop('zhaysan')
    print(fish_props)
    fish_weight_3d = get_fish_weight_3d('zhaysan', ['лещ', 'судак', 'плотва'])
    # print(fish_weight_3d.sel(FishType='лещ'))
    # print(fish_weight_3d.sel(FishType='судак').to_pandas())
    # print(fish_weight_3d.sel(FishType='судак').LessAge.values)
    # print(fish_weight_3d.sel(LessAge='less_15'))

