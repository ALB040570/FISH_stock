
import xarray as xr
from get_yearly_stock_3d import get_yearly_stock_net_out_ages_on_stock_3d, get_yearly_stock_net_with_ages_on_stock_3d, \
    get_yearly_stock_seine_out_ages_on_stock_3d, get_yearly_stock_seine_with_ages_on_stock_3d, get_yearly_stock_net_out_ages_on_catch_3d, \
    get_yearly_stock_net_with_ages_on_catch_3d, get_yearly_stock_seine_out_ages_on_catch_3d, get_yearly_stock_seine_with_ages_on_catch_3d
from get_stock_npc import get_stock_npc_3d
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from get_catchability_3d import get_catchability_net_3d, get_catchability_seine_3d
from get_stock_bayes_3d import get_stock_bayes_net_3d, get_stock_bayes_seine_3d, get_stock_bayes_twogear
from get_stock_bayes_3d import get_stock_bayes_twogear

stock_npc = get_stock_npc_3d('zhaysan')

yearly_stock_net_out_ages_on_stock = get_yearly_stock_net_out_ages_on_stock_3d('zhaysan')
yearly_stock_net_with_ages_on_stock = get_yearly_stock_net_with_ages_on_stock_3d('zhaysan')
yearly_stock_seine_out_ages_on_stock = get_yearly_stock_seine_out_ages_on_stock_3d('zhaysan')
yearly_stock_seine_with_ages_on_stock = get_yearly_stock_seine_with_ages_on_stock_3d('zhaysan')
yearly_stock_net_out_ages_on_catch = get_yearly_stock_net_out_ages_on_catch_3d('zhaysan')
yearly_stock_net_with_ages_on_catch = get_yearly_stock_net_with_ages_on_catch_3d('zhaysan')
yearly_stock_seine_out_ages_on_catch = get_yearly_stock_seine_out_ages_on_catch_3d('zhaysan')
yearly_stock_seine_with_ages_on_catch = get_yearly_stock_seine_with_ages_on_catch_3d('zhaysan')
# stock_bayes_net_out_ages = get_stock_bayes_net_3d('zhaysan', False)
# stock_bayes_net_out_ages = stock_bayes_net_out_ages.swap_dims({'age': 'LessAge'})
# stock_bayes_net_out_ages = stock_bayes_net_out_ages[:, :, 1:]
# stock_bayes_net_with_ages = get_stock_bayes_net_3d('zhaysan', True)
# stock_bayes_net_with_ages = stock_bayes_net_with_ages.swap_dims({'age': 'LessAge'})
# stock_bayes_net_with_ages = stock_bayes_net_with_ages[:, :, 1:]
# stock_bayes_seine = get_stock_bayes_seine_3d('zhaysan', False)
# stock_bayes_seine = stock_bayes_seine.swap_dims({'age': 'LessAge'})
# stock_bayes_seine = stock_bayes_seine[:, :, 1:]
# stock_bayes_togear_2 = get_stock_bayes_twogear('zhaysan', False)
# stock_bayes_togear_2 = stock_bayes_togear_2.swap_dims({'age': 'LessAge'})
# stock_bayes_togear_2 = stock_bayes_togear_2[:, :, 1:]
stock_bayes_onegear_net_with_ages_00 = get_stock_bayes_net_3d('zhaysan', True, 'test00')['X_median']
stock_bayes_onegear_net_with_ages_00 = stock_bayes_onegear_net_with_ages_00.swap_dims({'age': 'LessAge'})
stock_bayes_onegear_net_with_ages_00 = stock_bayes_onegear_net_with_ages_00[:, :, 1:]
stock_bayes_onegear_seine_with_ages_00 = get_stock_bayes_seine_3d('zhaysan', True, 'test00')['X_median']
stock_bayes_onegear_seine_with_ages_00 = stock_bayes_onegear_seine_with_ages_00.swap_dims({'age': 'LessAge'})
stock_bayes_onegear_seine_with_ages_00 = stock_bayes_onegear_seine_with_ages_00[:, :, 1:]
stock_bayes_twogear_with_ages_00 = get_stock_bayes_twogear('zhaysan', True, 'test00')['X_median']
stock_bayes_twogear_with_ages_00 = stock_bayes_twogear_with_ages_00.swap_dims({'age': 'LessAge'})
stock_bayes_twogear_with_ages_00 = stock_bayes_twogear_with_ages_00[:, :, 1:]
stock_bayes_onegear_net_with_ages_01 = get_stock_bayes_net_3d('zhaysan', True, 'test01')['X_median']
stock_bayes_onegear_net_with_ages_01 = stock_bayes_onegear_net_with_ages_01.swap_dims({'age': 'LessAge'})
stock_bayes_onegear_net_with_ages_01 = stock_bayes_onegear_net_with_ages_01[:, :, 1:]
stock_bayes_twogear_with_ages_77 = get_stock_bayes_twogear('zhaysan', True, 'test77')['X_median']
stock_bayes_twogear_with_ages_77 = stock_bayes_twogear_with_ages_77.swap_dims({'age': 'LessAge'})
stock_bayes_twogear_with_ages_77 = stock_bayes_twogear_with_ages_77[:, :, 1:]
stock_bayes_twogear_with_ages_22 = get_stock_bayes_twogear('zhaysan', True, 'test22')['X_median']
stock_bayes_twogear_with_ages_22 = stock_bayes_twogear_with_ages_22.swap_dims({'age': 'LessAge'})
stock_bayes_twogear_with_ages_22 = stock_bayes_twogear_with_ages_22[:, :, 1:]
stock_bayes_twogear_with_ages_33 = get_stock_bayes_twogear('zhaysan', True, 'test33')['X_median']
stock_bayes_twogear_with_ages_33 = stock_bayes_twogear_with_ages_33.swap_dims({'age': 'LessAge'})
stock_bayes_twogear_with_ages_33 = stock_bayes_twogear_with_ages_33[:, :, 1:]
stock_bayes_twogear_with_ages_44 = get_stock_bayes_twogear('zhaysan', True, 'test44')['X_median']
stock_bayes_twogear_with_ages_44 = stock_bayes_twogear_with_ages_44.swap_dims({'age': 'LessAge'})
stock_bayes_twogear_with_ages_44 = stock_bayes_twogear_with_ages_44[:, :, 1:]




# добавляем новое измерение Method
yearly_stock_net_out_ages_on_catch = yearly_stock_net_out_ages_on_catch.expand_dims(Method=["Оценка запаса на основе выловов балансовым методом без учета возрастов"])
yearly_stock_net_with_ages_on_catch = yearly_stock_net_with_ages_on_catch.expand_dims(Method=["Оценка запаса на основе выловов балансовым методом с учетом возрастов"])
yearly_stock_seine_out_ages_on_catch = yearly_stock_seine_out_ages_on_catch.expand_dims(Method=["Оценка запаса на основе выловов методом площадей без учета возрастов"])
yearly_stock_seine_with_ages_on_catch = yearly_stock_seine_with_ages_on_catch.expand_dims(Method=["Оценка запаса на основе выловов методом площадей с учетом возрастов"])
yearly_stock_net_out_ages_on_stock = yearly_stock_net_out_ages_on_stock.expand_dims(Method=["Оценка запаса на основе запасов балансовым методом без учета возрастов"])
yearly_stock_net_with_ages_on_stock = yearly_stock_net_with_ages_on_stock.expand_dims(Method=["Оценка запаса на основе запасов балансовым методом с учетом возрастов"])
yearly_stock_seine_out_ages_on_stock = yearly_stock_seine_out_ages_on_stock.expand_dims(Method=["Оценка запаса на основе запасов методом площадей без учета возрастов"])
yearly_stock_seine_with_ages_on_stock = yearly_stock_seine_with_ages_on_stock.expand_dims(Method=["Оценка запаса на основе запасов методом площадей с учетом возрастов"])
stock_npc_da = stock_npc.expand_dims(Method=["Оценка запаса научно-производственным центром РХ"])
# stock_bayes_net_out_ages = stock_bayes_net_out_ages.expand_dims(Method=['Оценка запаса байесовским методом для сетей без учета возрастов'])
# stock_bayes_net_with_ages = stock_bayes_net_with_ages.expand_dims(Method=['Оценка запаса байесовским методом для сетей с учетом возрастов'])
# stock_bayes_seine = stock_bayes_seine.expand_dims(Method=['Оценка запаса байесовским методом для невода'])
# stock_bayes_togear_2 = stock_bayes_togear_2.expand_dims(Method=["Оценка запаса общим байесовским методом"])
stock_bayes_onegear_net_with_ages_00 = stock_bayes_onegear_net_with_ages_00.expand_dims(Method=['Оценка байесовским методом для сети 1 правдопод test00'])
stock_bayes_onegear_seine_with_ages_00 = stock_bayes_onegear_seine_with_ages_00.expand_dims(Method=['Оценка байесовским методом для невода 1 правдопод test00'])
stock_bayes_twogear_with_ages_00 = stock_bayes_twogear_with_ages_00.expand_dims(Method=['Оценка байесовским методом для обоих test00'])
stock_bayes_onegear_net_with_ages_01 = stock_bayes_onegear_net_with_ages_01.expand_dims(Method=['Оценка байесовским методом для сети 2 правдопод test01'])
# stock_bayes_onegear_seine_with_ages_01 = stock_bayes_onegear_seine_with_ages_01.expand_dims(Method=['Оценка байесовским методом для невода 2 правдопод test01'])
stock_bayes_twogear_with_ages_77 = stock_bayes_twogear_with_ages_77.expand_dims(Method=['Оценка байесовским методом для обоих test77'])
stock_bayes_twogear_with_ages_22 = stock_bayes_twogear_with_ages_22.expand_dims(Method=['Оценка байесовским методом для обоих test22'])
stock_bayes_twogear_with_ages_33 = stock_bayes_twogear_with_ages_33.expand_dims(Method=['Оценка байесовским методом для обоих test33'])
stock_bayes_twogear_with_ages_44 = stock_bayes_twogear_with_ages_44.expand_dims(Method=['Оценка байесовским методом для обоих test44'])





yearly_stock_4d = xr.concat([
    yearly_stock_net_out_ages_on_catch,
    yearly_stock_net_with_ages_on_catch,
    yearly_stock_seine_out_ages_on_catch,
    yearly_stock_seine_with_ages_on_catch,
    # yearly_stock_net_out_ages_on_stock,
    # yearly_stock_net_with_ages_on_stock,
    # yearly_stock_seine_out_ages_on_stock,
    # yearly_stock_seine_with_ages_on_stock,
    stock_npc_da,
    stock_bayes_onegear_net_with_ages_00,
    stock_bayes_onegear_seine_with_ages_00,
    stock_bayes_twogear_with_ages_00,
    stock_bayes_onegear_net_with_ages_01,
    stock_bayes_twogear_with_ages_77,
    stock_bayes_twogear_with_ages_22,
    stock_bayes_twogear_with_ages_33,
    stock_bayes_twogear_with_ages_44
], dim='Method', join='outer')

catchability_net_3d = get_catchability_net_3d('zhaysan')
catchability_seine_3d = get_catchability_seine_3d('zhaysan')
catchability_net_4d = catchability_net_3d.expand_dims(Instrument=["Сеть"])
catchability_seine_4d = catchability_seine_3d.expand_dims(Instrument=["Невод"])
catchability_4d = xr.concat([catchability_net_4d, catchability_seine_4d], dim='Instrument', join='outer')


# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(layout="wide", page_title="Оценки запасов рыбных ресурсов различными методами")


tab_table, tab_figure_1, tab_figure_2, catchability_figure_3 = st.tabs([
    'Таблица оценки запасов разными методами',
    'Графики оценки запасов по годам',
    'Графики оценки запасов по возрастам',
    'Графики коэффициентов уловистости'
])

with tab_table:
    st.subheader("Таблица оценки запасов различными методами в шт.")
    # Выпадающие списки внутри вкладки
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([0.05, 0.4, 0.1, 0.4, 0.05])
        with c2:
            selected_fish_1 = c2.selectbox("Вид рыбы", yearly_stock_4d.FishType.values, key='fish_1')

    st.divider()

    # Вырезаем трехмерный куб фиксируя рыбу
    yearly_stock_fish = yearly_stock_4d.sel(FishType=selected_fish_1)

    df_yearly_stock_fish = yearly_stock_fish.to_dataframe(name='запас').reset_index()

    age_mapping = dict(zip(df_yearly_stock_fish["LessAge"], df_yearly_stock_fish["age"]))

    # Сортируем текстовые колонки LessAge по их реальному цифровому возрасту
    sorted_less_ages = sorted(age_mapping.keys(), key=lambda x: age_mapping[x])

    # Разворачиваем в "широкий" формат (pivot)
    df_yearly_stock_fish_pivot = df_yearly_stock_fish.pivot_table(
        index=['Year', 'Method'],
        columns='LessAge',
        values='запас'
    )

    # 5. Сортируем колонки по возрастанию возраста и добавляем столбец Сумма
    df_yearly_stock_fish_pivot = df_yearly_stock_fish_pivot[sorted_less_ages]
    df_yearly_stock_fish_pivot['Сумма'] = df_yearly_stock_fish_pivot.sum(axis=1)

    # Переименовываем текстовые less_x в "Возраст x"
    df_yearly_stock_fish_pivot = df_yearly_stock_fish_pivot.rename(
        columns={less_age: f"Возраст {age_mapping[less_age]}" for less_age in sorted_less_ages}
    )

    # Сбрасываем индекс, чтобы Year и Method стали обычными колонками
    df_yearly_stock_fish_pivot = df_yearly_stock_fish_pivot.reset_index()

    # НАСТРОЙКА ФОРМАТА КОЛОНОК (column_config)
    # Динамически создаем округление в целые числа (%d) для всех колонок, кроме Year и Method
    config = {
        "Year": st.column_config.NumberColumn("Год", format="%d"),
        "Method": st.column_config.TextColumn("Метод")
    }
    # Добавляем конфигурацию для каждого возраста и для суммы
    for col in df_yearly_stock_fish_pivot.columns:
        if col not in ["Year", "Method"]:
            config[col] = st.column_config.NumberColumn(format="%,d")

    # config = {col: st.column_config.NumberColumn(format="%d") for col in 'LessAge'}

    # Отображаем итоговую интерактивную таблицу в Streamlit
    st.dataframe(
        df_yearly_stock_fish_pivot,
        width='stretch', # В актуальных версиях streamlit вместо width='stretch' используется этот параметр
        height=700,
        column_config=config,
        # hide_index=True # Скрываем системный индекс pandas (0, 1, 2...), оставляя только наши данные
    )

    # st.dataframe(df_yearly_stock_fish_pivot,
    #              width='stretch',
    #              height=700,
    #              column_config=config)

with tab_figure_1:
    st.subheader('Графики оценки запасов разными методами по годам')
    # Выпадающие списки внутри вкладки
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([0.05, 0.4, 0.1, 0.4, 0.05])
        with c2:
            selected_fish_3 = c2.selectbox("Вид рыбы", yearly_stock_4d.FishType.values, key='fish_3')
        with c4:
            age_options_1 = ['все возрасты'] + list(yearly_stock_4d.LessAge.values)
            selected_age_1 = c4.selectbox("Возраст рыбы", age_options_1, key='age_1')

    st.divider()

    if selected_age_1 == 'все возрасты':
        res = yearly_stock_4d.sel(FishType=selected_fish_3).sum('LessAge')
    else:
        res = yearly_stock_4d.sel(FishType=selected_fish_3, LessAge=selected_age_1)

    df_yearly_stock_fish_by_year = res.to_dataframe(name='запас').reset_index()

    # 4. Строим интерактивный график в Plotly
    fig_1 = px.line(
        df_yearly_stock_fish_by_year,
        x="Year",  # По оси X — годы
        y="запас",  # По оси Y — значения запаса
        color="Method",  # Разделение линий по цветам (методы уходят в легенду)
        markers=True,  # Добавляем точки на изломах линий для наглядности
        title=f"Сравнение методов оценки запаса для: {selected_fish_3} ({selected_age_1} возраста)",
        labels={
            "Year": "годы",
            "запас": "Запас",
            "Method": "Метод оценки",
        },
    )

    fig_1.update_layout(
        xaxis=dict(
            tickmode="linear",  # Показываем каждый возраст без дробных частей
            dtick=1,
        ),
        hovermode="x unified",  # Единая подсказка для всех линий при наведении
        margin=dict(l=20, r=150, t=60, b=50),  # Увеличиваем правый отступ (r=150), чтобы освободить место под легенду

        # --- НАСТРОЙКА ВНЕШНЕЙ ЛЕГЕНДЫ ---
        showlegend=True,
        legend=dict(
            orientation="v",  # Вертикальное расположение элементов
            yanchor="middle",  # Центрируем легенду по вертикали
            y=0.5,  # Располагаем ровно по центру высоты графика
            xanchor="left",  # Привязываем левый край легенды
            x=1.05,  # Выносим за правый край (1.0 — это крайняя правая граница графика) [1]
            bordercolor="LightGrey",  # Добавляем аккуратную рамку вокруг легенды (опционально)
            borderwidth=1
        )
    )

    # Форматируем всплывающие подсказки, добавляя разделение тысяч пробелами
    fig_1.update_traces(hovertemplate="%{y:,.0f}")

    # 6. Отображаем график в Streamlit
    st.plotly_chart(fig_1)

with tab_figure_2:
    st.subheader('Графики оценки запасов разными методами по возрастам')
    # Выпадающие списки внутри вкладки
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([0.05, 0.4, 0.1, 0.4, 0.05])
        with c2:
            selected_fish_2 = c2.selectbox("Вид рыбы", yearly_stock_4d.FishType.values, key='fish_2')
        with c4:
            selected_year_1 = c4.selectbox("Год", yearly_stock_4d.Year.values, key='year_1')

    st.divider()

    yearly_stock_fish = yearly_stock_4d.sel(FishType=selected_fish_2, Year=selected_year_1)
    df_yearly_stock_fish = yearly_stock_fish.to_dataframe(name='запас').reset_index()
    # Сортируем по реальному числовому возрасту 'age', чтобы ось X шла строго по порядку (2, 3, 4...)
    df_yearly_stock_fish = df_yearly_stock_fish.sort_values(by="age")

    # 4. Строим интерактивный график в Plotly
    fig_2 = px.line(
        df_yearly_stock_fish,
        x="age",  # По оси X — числовые возрасты рыб
        y="запас",  # По оси Y — значения запаса
        color="Method",  # Разделение линий по цветам (методы уходят в легенду)
        markers=True,  # Добавляем точки на изломах линий для наглядности
        title=f"Сравнение методов оценки запаса для: {selected_fish_2} ({selected_year_1} год)",
        labels={
            "age": "Возраст рыбы (лет)",
            "запас": "Запас",
            "Method": "Метод оценки",
        },
    )

    # Стилизация графика для лучшей читаемости
    # fig.update_layout(
    #     xaxis=dict(
    #         tickmode="linear",  # Показываем каждый возраст (без дробных подписей вроде 2.5)
    #         dtick=1,
    #     ),
    #     hovermode="x unified",  # При наведении на график будут видны значения всех методов одновременно
    #     margin=dict(l=20, r=20, t=50, b=20),
    #     legend=dict(
    #         orientation="h",  # Переносим легенду наверх/горизонтально для экономии места
    #         yanchor="top",
    #         y=1.02,
    #         xanchor="right",
    #         x=1,
    #     ),
    # )

    fig_2.update_layout(
        xaxis=dict(
            tickmode="linear",  # Показываем каждый возраст без дробных частей
            dtick=1,
        ),
        hovermode="x unified",  # Единая подсказка для всех линий при наведении
        margin=dict(l=20, r=150, t=60, b=50),  # Увеличиваем правый отступ (r=150), чтобы освободить место под легенду

        # --- НАСТРОЙКА ВНЕШНЕЙ ЛЕГЕНДЫ ---
        showlegend=True,
        legend=dict(
            orientation="v",  # Вертикальное расположение элементов
            yanchor="middle",  # Центрируем легенду по вертикали
            y=0.5,  # Располагаем ровно по центру высоты графика
            xanchor="left",  # Привязываем левый край легенды
            x=1.05,  # Выносим за правый край (1.0 — это крайняя правая граница графика) [1]
            bordercolor="LightGrey",  # Добавляем аккуратную рамку вокруг легенды (опционально)
            borderwidth=1
        )
    )

    # Форматируем всплывающие подсказки, добавляя разделение тысяч пробелами
    fig_2.update_traces(hovertemplate="%{y:,.0f}")

    # 6. Отображаем график в Streamlit
    st.plotly_chart(fig_2)

with catchability_figure_3:
    st.subheader('Графики коэффициентов уловистости по возрастам')
    # Выпадающие списки внутри вкладки
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([0.05, 0.4, 0.1, 0.4, 0.05])
        with c2:
            # Берем первую доступную рыбу как дефолт, обернув в список: [catchability_4d.FishType.values[0]]
            default_fish = [catchability_4d.FishType.values[0]] if len(catchability_4d.FishType.values) > 0 else []

            selected_fish_4 = c2.multiselect("Вид рыбы", catchability_4d.FishType.values, default=default_fish, key='fish_4')
        with c4:
            selected_year_2 = c4.selectbox("Год", catchability_4d.Year.values, key='year_2')

    st.divider()

    catchability_4d_filtered = catchability_4d.sel(FishType=selected_fish_4, Year=selected_year_2)
    df_catchability_4d_filtered = catchability_4d_filtered.to_dataframe(name='коэффициент уловистости').reset_index()
    # Сортируем по реальному числовому возрасту 'age', чтобы ось X шла строго по порядку (2, 3, 4...)
    df_catchability_4d_filtered = df_catchability_4d_filtered.sort_values(by="age")

    # 4. РЕШЕНИЕ: Создаем объединенную колонку для легенды (явно приводим к строкам)
    df_catchability_4d_filtered["Вид рыбы и орудие лова"] = (
        df_catchability_4d_filtered["Instrument"].astype(str) + " — " +
        df_catchability_4d_filtered["FishType"].astype(str)
    )

    # 4. Строим интерактивный график в Plotly
    fig_3 = px.line(
        df_catchability_4d_filtered,
        x="age",  # По оси X — числовые возрасты рыб
        y="коэффициент уловистости",  # По оси Y — значения запаса
        color="Вид рыбы и орудие лова",  # Разделение линий по цветам (методы уходят в легенду)
        markers=True,  # Добавляем точки на изломах линий для наглядности
        title=f"Сравнение коэффициентов уловистости: {selected_fish_4} ({selected_year_2} год)",
        labels={
            "age": "Возраст рыбы (лет)",
            "коэффициент уловистости": "коэффициент уловистости",
            "Instrument": "Орудия лова",
        },
    )

    fig_3.update_layout(
        xaxis=dict(
            tickmode="linear",  # Показываем каждый возраст без дробных частей
            dtick=1,
        ),
        hovermode="x unified",  # Единая подсказка для всех линий при наведении
        margin=dict(l=20, r=150, t=60, b=50),  # Увеличиваем правый отступ (r=150), чтобы освободить место под легенду

        # --- НАСТРОЙКА ВНЕШНЕЙ ЛЕГЕНДЫ ---
        showlegend=True,
        legend=dict(
            orientation="v",  # Вертикальное расположение элементов
            yanchor="middle",  # Центрируем легенду по вертикали
            y=0.5,  # Располагаем ровно по центру высоты графика
            xanchor="left",  # Привязываем левый край легенды
            x=1.05,  # Выносим за правый край (1.0 — это крайняя правая граница графика) [1]
            bordercolor="LightGrey",  # Добавляем аккуратную рамку вокруг легенды (опционально)
            borderwidth=1
        )
    )

    # Форматируем всплывающие подсказки, добавляя разделение тысяч пробелами
    fig_3.update_traces(hovertemplate="%{y:,.3f}")

    # 6. Отображаем график в Streamlit
    st.plotly_chart(fig_3)



