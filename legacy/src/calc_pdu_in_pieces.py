import xarray as xr
import pandas as pd
import numpy as np

from get_fish_prop import get_fish_prop, get_fish_weight_3d
from get_yearly_stock_3d import get_yearly_stock_net_out_ages_on_stock_3d, get_yearly_stock_net_with_ages_on_stock_3d, get_yearly_stock_seine_out_ages_on_stock_3d, get_yearly_stock_seine_with_ages_on_stock_3d
from get_stock_npc import get_pdu_tons_2d


# gear - орудие лова, принимает два значения: 'сеть' и 'невод'
# with_ages, если True - то на основе данных с учетом возрастов, если False - на основе данных без учета возрастов
def calc_pdu_in_pieces(waterbody_name: str, gear: str, with_ages: bool):
    fish_props = get_fish_prop(waterbody_name)
    fish_types = list(fish_props['виды рыб'].keys())
    # print('виды рыб ', type(fish_types), '   ', fish_types)
    m0_dict = fish_props['возраст половой зрелости']
    m1_dict = fish_props['максимальный возраст']
    m2_dict = fish_props['возраст для хищников']

    fish_weight_3d = get_fish_weight_3d('zhaysan', fish_types)
    fish_weight_3d = fish_weight_3d.swap_dims({"LessAge": "age"})
    # print('средний вес ', fish_weight_3d.shape, fish_weight_3d.dims, fish_weight_3d.FishType.values)

    yearly_stock_3d = get_yearly_stock_net_out_ages_on_stock_3d(waterbody_name)
    if gear == 'сеть' and with_ages:
        yearly_stock_3d = get_yearly_stock_net_with_ages_on_stock_3d(waterbody_name)
    elif gear == 'невод' and not with_ages:
        yearly_stock_3d = get_yearly_stock_seine_out_ages_on_stock_3d(waterbody_name)
    elif gear == 'невод' and with_ages:
        yearly_stock_3d = get_yearly_stock_seine_with_ages_on_stock_3d(waterbody_name)

    # Заменяем строковое измерение 'LessAge' на числовое 'age'
    yearly_stock_3d = yearly_stock_3d.swap_dims({"LessAge": "age"})

    fish_weight_3d, yearly_stock_3d = xr.align(fish_weight_3d, yearly_stock_3d)

    pdu_tons_2d = get_pdu_tons_2d(waterbody_name)

    # print('кол-во рыб  = ', yearly_stock_3d.shape, yearly_stock_3d.dims)

    # 2. Считаем общую биомассу запаса в тоннах (штуки * граммы / 1 000 000)
    # Массивы stock_3d и fish_weight_3d имеют измерения (Year, FishType, LessAge)
    yearly_stock_biomass_3d = (yearly_stock_3d * fish_weight_3d) / 1000000

    # Переводим обычный словарь Python в xarray.DataArray
    maturity_da = xr.DataArray(
        list(m0_dict.values()),
        coords={"FishType": list(m0_dict.keys())},
        dims=["FishType"]
    )

    maturity_da = maturity_da.sel(
        FishType=yearly_stock_biomass_3d.FishType
    )

    # Применяем биологические ограничения к БИОМАССЕ
    # Ограничение 1: Половозрелость (например, через ваш словарь maturity_age_dict)
    is_mature_3d = yearly_stock_biomass_3d.where(yearly_stock_biomass_3d.age >= maturity_da, 0.0)

    is_mature_3d = is_mature_3d.sel(
        Year=yearly_stock_biomass_3d.Year,
        FishType=yearly_stock_biomass_3d.FishType,
        age=yearly_stock_biomass_3d.age
    )

    # Ограничение 2: Максимальный возраст (где вес рыбы > 0)
    has_weight_3d = fish_weight_3d > 0

    # 1. Принудительно перестраиваем маску has_weight_3d под точный порядок и состав координат целевого куба
    has_weight_3d = has_weight_3d.sel(
        Year=yearly_stock_biomass_3d.Year,
        FishType=yearly_stock_biomass_3d.FishType,
        age=yearly_stock_biomass_3d.age
    )

    # Объединяем последовательно, чтобы избежать ошибки bitwise_and
    allowed_mask_3d = xr.where(is_mature_3d, True, False) & xr.where(has_weight_3d, True, False)

    # print(allowed_mask_3d, allowed_mask_3d.shape, allowed_mask_3d.dims, allowed_mask_3d.FishType.values)

    # --- 3. ИНИЦИАЛИЗАЦИЯ ДЛЯ ЦИКЛА КОРРЕКТИРОВКИ ОДУ ---
    pdu_grams_2d = pdu_tons_2d * 1000000  # Переводим ОДУ в граммы
    total_catch_pieces_3d = xr.zeros_like(yearly_stock_3d)  # Сюда копим итоговый улов в штуках

    # Запускаем 3 итерации перераспределения. Если где-то квота упрется в потолок запаса,
    # остаток распределится на другие возраста на следующем шаге.
    for iteration in range(3):
        # Текущий доступный остаток запаса в штуках
        current_stock_pieces = yearly_stock_3d - total_catch_pieces_3d

        # Считаем доступную биомассу для текущего шага
        current_biomass_3d = (current_stock_pieces * fish_weight_3d).where(allowed_mask_3d, 0.0)

        # --- МЕХАНИЗМ 1: ПОВЫШАЮЩИЙ КОЭФФИЦИЕНТ СЕЛЕКТИВНОСТИ (НАГРУЗКИ) ---
        # Линейно увеличиваем привлекательность рыбы с ростом её числового возраста 'age'
        # Умножаем возраст на 0.1 (например, для 2 лет коэффициент 0.2, для 10 лет — 1.0)
        selectivity_3d = current_biomass_3d.age * 0.1
        weighted_biomass_3d = current_biomass_3d * selectivity_3d

        # Схлопываем ось возрастов, чтобы найти сумму по группе (Год, Вид рыбы)
        total_weighted_biomass_2d = weighted_biomass_3d.sum(dim="age")

        # Если ловить больше некого (вся рыба выбрана), останавливаем цикл
        if (total_weighted_biomass_2d == 0).all():
            break

        # Считаем доли изъятия (теперь у старших возрастов доля будет значительно выше!)
        age_share_3d = weighted_biomass_3d / total_weighted_biomass_2d.where(total_weighted_biomass_2d > 0, 1.0)

        # Распределяем остаток ОДУ по возрастам на этом шаге (в граммах)
        catch_grams_step = pdu_grams_2d * age_share_3d

        # Переводим улов шага в штуки рыб
        catch_pieces_step = catch_grams_step / fish_weight_3d.where(fish_weight_3d > 0, 1.0)
        catch_pieces_step = catch_pieces_step.fillna(0.0)

        # --- МЕХАНИЗМ 2: КОРРЕКТИРОВКА (Срезание по потолку запаса) ---
        # Улов этого шага не может превысить физический остаток рыбы в море
        catch_pieces_allowed = xr.where(catch_pieces_step > 0.75 * current_stock_pieces, 0.75 * current_stock_pieces,
                                        catch_pieces_step)

        # Добавляем одобренный улов в общий накопитель штук
        total_catch_pieces_3d = total_catch_pieces_3d + catch_pieces_allowed

        # Считаем, сколько ГРАММ квоты мы физически изъяли на этом шаге
        grams_taken_step = catch_pieces_allowed * fish_weight_3d
        total_grams_taken_2d = grams_taken_step.sum(dim="age")

        # Вычитаем из оставшегося ОДУ то, что только что успешно распределили
        pdu_grams_2d = pdu_grams_2d - total_grams_taken_2d
        pdu_grams_2d = pdu_grams_2d.where(pdu_grams_2d > 0, 0.0)

    # final_catch_pieces_3d — ваш идеальный трехмерный куб улова в штуках рыб!
    final_catch_pieces_3d = total_catch_pieces_3d.swap_dims({'age': 'LessAge'})

    # print(final_catch_pieces_3d, final_catch_pieces_3d.shape, final_catch_pieces_3d.dims)

    return final_catch_pieces_3d


if __name__ == '__main__':
    pdu_net_out_ages_3d = calc_pdu_in_pieces('zhaysan', 'сеть', False)
    pdu_net_with_ages_3d = calc_pdu_in_pieces('zhaysan', 'еть', True)
    pdu_seine_out_ages_3d = calc_pdu_in_pieces('zhaysan', 'невод', False)
    pdu_seine_with_ages_3d = calc_pdu_in_pieces('zhaysan', 'невод', True)

    fish_props = get_fish_prop('zhaysan')
    fish_types = list(fish_props['виды рыб'].keys())
    print('виды рыб ', type(fish_types), '   ', fish_types)
    m0_dict = fish_props['возраст половой зрелости']
    m1_dict = fish_props['максимальный возраст']
    m2_dict = fish_props['возраст для хищников']

    fish_weight_3d = get_fish_weight_3d('zhaysan', fish_types)

    # Переводим итоговый улов обратно в тонны
    pdu_tons_net_out_ages_3d = (pdu_net_out_ages_3d * fish_weight_3d) / 1000000
    pdu_tons_net_out_ages_2d = pdu_tons_net_out_ages_3d.sum(dim="LessAge")

    print('pdu_tons_net_out_ages_3d = /n', pdu_tons_net_out_ages_2d.to_pandas())

    # Переводим итоговый улов обратно в тонны
    pdu_tons_net_with_ages_3d = (pdu_net_with_ages_3d * fish_weight_3d) / 1000000
    pdu_tons_net_with_ages_2d = pdu_tons_net_with_ages_3d.sum(dim="LessAge")

    print('pdu_tons_net_with_ages_3d = /n', pdu_tons_net_with_ages_2d.to_pandas())

    # Переводим итоговый улов обратно в тонны
    pdu_tons_seine_out_ages_3d = (pdu_seine_out_ages_3d * fish_weight_3d) / 1000000
    pdu_tons_seine_out_ages_2d = pdu_tons_seine_out_ages_3d.sum(dim="LessAge")

    print('pdu_tons_seine_out_ages_3d = /n', pdu_tons_seine_out_ages_2d.to_pandas())

    # Переводим итоговый улов обратно в тонны
    pdu_tons_seine_with_ages_3d = (pdu_seine_with_ages_3d * fish_weight_3d) / 1000000
    pdu_tons_seine_with_ages_2d = pdu_tons_seine_with_ages_3d.sum(dim="LessAge")

    print('pdu_tons_seine_with_ages_3d = /n', pdu_tons_seine_with_ages_2d.to_pandas())

    print('редний вес ')
    print(fish_weight_3d.sel(Year=2015).to_pandas())

    print('результат для сети без учета возрастов')
    print(pdu_net_out_ages_3d.sel(FishType='лещ').sum('LessAge'))
    print(pdu_seine_out_ages_3d.sel(FishType='лещ').sum('LessAge'))
    #print(final_pdu_net_out_3d.sum('age').to_pandas())
    #print(final_pdu_net_out_3d.sel(FishType='судак').to_pandas())
