import pandas as pd

from data_catch.zhaysan_fish_prop import k_catchability_1


# Ядро альтернативного алгоритма
# рассчитывает долю рыб первого кольца по часам в сети и кольцах.
def calc_model_for_net(k_catchability, hours, net_width, fish_speed):
    """
    Базовое математическое ядро модели.
    k_catchability: коэффициент уловистости
    hours: время стоянки сети
    net_width: длина сети
    fish_speed: скорость блуждания рыбы

    Возвращает:
        df - детальная таблица по часам
        final_state - словарь состояния на последнем часу
    """
    num_rings = hours

    r0 = net_width / 2.0
    r1 = fish_speed

    if r0 >= r1:
        raise ValueError(
            f"Ошибка: Половина ширины сети ({r0}м) не должна превышать скорость рыбы ({r1}м/ч)."
        )

    total_areas = 1 + hours
    fish = [0.0] * total_areas

    # ИСПРАВЛЕНО: Записываем значения строго по индексам списка
    fish[0] = (r0 / r1) ** 2  # Круг 0
    fish[1] = 1.0 - (r0 / r1) ** 2  # Кольцо 1

    # Заполняем остальные кольца (2, 3 ... N) нечетными числами (3, 5, 7...)
    for idx in range(2, total_areas):
        fish[idx] = float(2 * idx - 1)

    in_net = 0.0
    history = []

    # Записываем Час 0
    row_0 = {"Час": 0, "Сеть": in_net, "Круг 0": fish[0]}
    for i in range(1, total_areas):
        row_0[f"Клц {i}"] = fish[i]
    row_0["Баланс"] = in_net + sum(fish)
    history.append(row_0)

    # Почасовое моделирование
    for hour in range(1, hours + 1):
        next_fish = [0.0] * total_areas

        p_in = [0.0] * total_areas
        p_out = [0.0] * total_areas

        # Нулевой круг: фиксировано по ТЗ
        p_in[0], p_out[0] = 0.25, 0.25

        # Первое кольцо: зависит от геометрии
        p_in[1] = 0.5 * r0 / (r0 + r1)
        p_out[1] = 0.5 * r1 / (r0 + r1)

        # Кольца со 2-го по последнее
        for idx in range(2, total_areas):
            total_w = float((idx - 1) + idx)
            p_in[idx] = 0.5 * (idx - 1) / total_w
            p_out[idx] = 0.5 * idx / total_w

        # Миграция и вылов
        caught_this_hour = p_in[0] * fish[0] * k_catchability
        in_net += caught_this_hour

        # Пересчет баланса зон
        next_fish[0] = (
                (0.5 * fish[0]) + ((1 - k_catchability) * p_in[0] * fish[0]) + (p_in[1] * fish[1])
        )
        next_fish[1] = (0.5 * fish[1]) + (p_out[0] * fish[0]) + (p_in[2] * fish[2])

        for idx in range(2, total_areas - 1):
            next_fish[idx] = (
                (0.5 * fish[idx])
                + (p_out[idx - 1] * fish[idx - 1])
                + (p_in[idx + 1] * fish[idx + 1])
            )

        next_fish[-1] = (
            (0.5 * fish[-1]) + (p_out[-2] * fish[-2]) + (p_out[-1] * fish[-1])
        )

        fish = next_fish

        # Записываем состояние часа
        row_hour = {"Час": hour, "Сеть": in_net, "Круг 0": fish[0]}
        for i in range(1, total_areas):
            row_hour[f"Клц {i}"] = fish[i]
        row_hour["Баланс"] = in_net + sum(fish)
        history.append(row_hour)

    df = pd.DataFrame(history)

    # Формируем итоговое состояние
    final_state = {"Сеть": in_net, "Круг 0": fish[0]}
    for i in range(1, total_areas):
        final_state[f"Кольцо {i}"] = fish[i]

    return df, final_state


if __name__ == '__main__':
    # k_catchability, hours, net_width, fish_speed
    k_catchability = 0.1
    hours = 12
    net_width = 25
    fish_speed = 1620
    df, final_state = calc_model_for_net(k_catchability, hours, net_width, fish_speed)
    # print('df = ', df)
    print('final_state = ', final_state)
    y = 1 / final_state['Сеть']
    print('1/X = ', 1 / final_state['Сеть'])
    print(y * 3000000000)
    _, final_state = calc_model_for_net(k_catchability, hours, net_width, 2* fish_speed)
    # print('df = ', df)
    print('final_state = ', final_state)
    y = 1 / final_state['Сеть']
    print('1/X = ', 1 / final_state['Сеть'])
    print(y * 3000000000)
