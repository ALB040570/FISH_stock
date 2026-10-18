import os
from pathlib import Path
import streamlit as st
import xarray as xr
import numpy as np
import plotly.graph_objects as go

# 1. Справочники соответствия видов рыб и файлов
fish_species = {
    "bream": "lesh8", "zander": "sudak4", "perch": "okun5", "roach": "plotva4",
    "pike": "shuka6", "carp": "sazan5", "crucian carp": "karas28", "ide": "yaz5"
}

fishes = list(fish_species.keys())

fishes_dict = {
    "bream": "лещ", "zander": "судак", "perch": "окунь", "roach": "плотва",
    "pike": "щука", "carp": "сазан", "crucian carp": "карась", "ide": "язь"
}

# Инициализация путей
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data_stock"

st.set_page_config(page_title="Анализ запасов по видам рыб", layout="wide")
st.title("🐟 Сравнительный анализ методов оценки запасов рыб")
st.markdown("Визуализация абсолютной динамики численности популяций в миллионах особей.")

# 2. Функция безопасной загрузки NetCDF
@st.cache_data(show_spinner=False)
def load_netcdf(file_name, is_dataset=False):
    path = DATA_DIR / file_name
    if not path.exists():
        return None
    try:
        # Унифицируем загрузку DataArray и Dataset
        ds = xr.open_dataset(path) if is_dataset else xr.open_dataarray(path)
        ds.load()
        return ds
    except Exception as e:
        st.error(f"Ошибка чтения файла {file_name}: {e}")
        return None

# Загрузка внешних массивов (Метод площадей = Сети, Балансовый метод = Невода)
ds_net = load_netcdf("zhaysan_yearly_stock_net_with_ages_on_catch_3d.nc")
ds_seine = load_netcdf("zhaysan_yearly_stock_seine_with_ages_on_catch_3d.nc")

if ds_net is not None:
    ds_net = ds_net.swap_dims({'LessAge': 'age'})
if ds_seine is not None:
    ds_seine = ds_seine.swap_dims({'LessAge': 'age'})

# 3. Сайдбар / Панель выбора вида рыбы
selected_fish = st.radio("Выберите вид рыбы для анализа:", fishes, horizontal=True)

# Определяем имя файла для выбранной рыбы
file_code = fish_species[selected_fish]
main_file_name = f"zhaysan_bayes_2g1p_with_ages_3d_{file_code}.nc"

# Загружаем основной файл результатов (Dataset)
ds_main = load_netcdf_main = load_netcdf(main_file_name, is_dataset=True)

if ds_main is None:
    st.error(f"❌ Не удалось загрузить основной файл результатов `{main_file_name}` для вида: {selected_fish}")
    st.stop()

# 4. ПОДГОТОВКА ДАННЫХ (Без нормирования, в абсолютных величинах)
years = ds_main.coords["Year"].values

# Метрика 1: Общая численность рыбы (Медиана)
total_stock_med = ds_main["X_median"].sum(dim="age").values

# Обрабатываем квантили общей численности (Корректное название для q25-q75 — 50% CI)
if "X_q25" in ds_main and "X_q75" in ds_main:
    total_stock_q25 = ds_main["X_q25"].sum(dim='age').values
    total_stock_q75 = ds_main["X_q75"].sum(dim='age').values
else:
    total_stock_q25, total_stock_q75 = None, None

# Метрика 2: Численность без мальков (Исключаем сеголеток — возраст 0)
no_infants_stock = ds_main["X_median"].isel({'age': slice(1, None)}).sum(dim='age').values

# Перевод названия для фильтрации во внешних файлах
fish_type = fishes_dict[selected_fish]

# 1. МЕТОД ПЛОЩАДЕЙ (строго из данных НЕВОДОВ -> ds_seine)
if ds_seine is not None and fish_type in ds_seine.coords.get("FishType", []):
    area_method_absolute = ds_seine.sel(FishType=fish_type).sum(dim="age").values
else:
    area_method_absolute = np.zeros(len(years))

# 2. БАЛАНСОВЫЙ МЕТОД (строго из данных СЕТЕЙ -> ds_net)
if ds_net is not None and fish_type in ds_net.coords.get("FishType", []):
    balance_method_absolute = ds_net.sel(FishType=fish_type).sum(dim="age").values
else:
    balance_method_absolute = np.zeros(len(years))


# Метрика 5: Извлечение суммарного ОДУ (ПДУ) для текущей рыбы
if "pdu_pcs" in ds_main:
    total_pdu_absolute = ds_main["pdu_pcs"].sum(dim="age_observed").values
elif "PDU" in ds_main:
    total_pdu_absolute = ds_main["PDU"].sum(dim="age_observed").values
else:
    total_pdu_absolute = np.zeros(len(years))

# 5. ПОСТРОЕНИЕ ГРАФИКА
fig = go.Figure()

# А. Доверительный интервал (Межквартильный размах 50%)
if total_stock_q25 is not None and total_stock_q75 is not None:
    fig.add_trace(go.Scatter(x=years, y=total_stock_q75, mode='lines', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(
        x=years, y=total_stock_q25, mode='lines', line=dict(width=0),
        fill='tonexty', fillcolor='rgba(52, 152, 219, 0.12)',
        name='50% CI (Interquartile range)', showlegend=True
    ))

# Б. Линия 1: Общая численность
fig.add_trace(go.Scatter(
    x=years, y=total_stock_med, mode='lines+markers',
    line=dict(color='#2980b9', width=3), name='Total number (Median)'
))

# В. Линия 2: Численность без мальков (Старше 1 года)
fig.add_trace(go.Scatter(
    x=years, y=no_infants_stock, mode='lines+markers',
    line=dict(color='#27ae60', width=2.5, dash='dash'), name='Number without fry (> 1 year)'
))

# Г. Линия 3: Метод площадей (Данные неводов)
fig.add_trace(go.Scatter(
    x=years, y=area_method_absolute, mode='lines+markers',
    line=dict(color='#e67e22', width=2),
    name='Estimation by the area method (Seines)'  # Метод площадей — это НЕВОДА
))

# Д. Линия 4: Балансовый метод (Данные сетей)
fig.add_trace(go.Scatter(
    x=years, y=balance_method_absolute, mode='lines+markers',
    line=dict(color='#9b59b6', width=2),
    name='Estimation by the balance method (Nets)'  # Балансовый метод — это СЕТИ
))


# Е. Линия 5: Промысловый ОДУ (ПДУ)
fig.add_trace(go.Scatter(
    x=years, y=total_pdu_absolute, mode='lines+markers',
    name='Total Allowable Catch (TAC)',
    line=dict(color='#e74c3c', width=3, dash='dot'),
    marker=dict(symbol='square', size=7)
))

# Настройки оформления (этот блок у вас уже есть)
fig.update_layout(
    title=dict(
        text=f"Relative dynamics and verification of assessment methods for the species: {selected_fish.upper()}",
        font=dict(size=16)
    ),
    xaxis_title="Years",
    yaxis_title="Fish population (millions of specimens)",
    template="plotly_white",
    hovermode="x unified",
    height=600,
    width=1000,
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.3,
        xanchor="center",
        x=0.5
    )
)

# !!! ВНИМАНИЕ: Удалите или закомментируйте старую строку st.plotly_chart(fig, width='stretch') здесь !!!

# ==============================================================================
# 6. АНАЛИЗ РАСПРЕДЕЛЕНИЯ ПО ВОЗРАСТАМ (РАСПРЕДЕЛЕНИЕ ПО ВКЛАДКАМ)
# ==============================================================================

# Создаем две вкладки
tab_verification, tab_age_structure = st.tabs([
    "📊 Верификация методов",
    "🐟 Возрастная структура популяции"
])

# Отображаем первый график строго внутри первой вкладки с уникальным key
with tab_verification:
    st.subheader("Сравнение методов оценки численности")
    st.plotly_chart(fig, use_container_width=True, key="verification_chart")

with tab_age_structure:
    st.subheader(f"Возрастная структура популяции за последние 5 лет: {selected_fish.upper()}")

    # 1. Отбираем последние 5 лет и координаты возрастов
    last_5_years = years[-5:]
    age_coords = ds_main.coords["age"].values

    # Извлекаем срез данных, чтобы оценить масштаб
    raw_data_5_years = ds_main["X_median"].sel(Year=last_5_years).values
    max_val = float(np.max(raw_data_5_years))

    # 2. АВТОМАТИЧЕСКИЙ ВЫБОР МАСШТАБА И ЕДИНИЦ ИЗМЕРЕНИЯ
    if max_val >= 1_000_000:
        scale_factor = 1_000_000
        y_label = "Population size (millions of specimens)"
        hover_unit = "млн"
    elif max_val >= 1_000:
        scale_factor = 1_000
        y_label = "Population size (thousands of specimens)"
        hover_unit = "тыс."
    else:
        scale_factor = 1.0
        y_label = "Population size (specimens)"
        hover_unit = "шт."

    # Цветовая палитра
    colors = ['#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78', '#2ca02c']

    fig_multi_bar = go.Figure()

    # 3. Добавляем столбики для каждого года с учетом масштабирования
    for i, year in enumerate(last_5_years):
        # Делим исходные значения на коэффициент масштабирования
        age_vector = ds_main["X_median"].sel(Year=year).values / scale_factor

        fig_multi_bar.add_trace(go.Bar(
            x=age_coords,
            y=age_vector,
            name=str(year),
            hovertemplate=f"Возраст: %{{x}} лет<br>Численность: %{{y:.2f}} {hover_unit}<extra></extra>"
        ))

    # 4. Настройки оформления по стандартам научных журналов
    fig_multi_bar.update_layout(
        title=dict(
            text=f"Age distribution dynamics of {selected_fish.upper()} (Last 5 years)",
            font=dict(size=14, color="black")
        ),
        xaxis=dict(
            title="Age (years)",
            tickmode='linear',
            tick0=0,
            dtick=1,
            gridcolor='rgba(200, 200, 200, 0.3)'
        ),
        yaxis=dict(
            title=y_label,  # Подпись оси теперь подставляется динамически!
            gridcolor='rgba(200, 200, 200, 0.3)'
        ),
        barmode='group',
        template="plotly_white",
        height=500,
        legend=dict(
            title="Years",
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5
        ),
        margin=dict(l=60, r=30, t=50, b=60)
    )

    st.plotly_chart(fig_multi_bar, use_container_width=True, key="multi_bar_chart")

    # ==============================================================================
    # ТАБЛИЦА ДЛЯ СТАТЬИ И ПРИЛОЖЕНИЯ (ВСЕ ГОДЫ, В ТОЧНЫХ ВЕЛИЧИНАХ)
    # ==============================================================================
    st.markdown("---")
    st.markdown("### 📋 Полные данные возрастной структуры по всем годам (для приложения к статье)")

    st.info(
        "📝 **Примечание для верстки статьи:** Ввиду большого количества столбцов "
        "данную таблицу рекомендуется размещать в **Приложении** на странице с **альбомной (ландшафтной) ориентацией**."
    )

    # 1. Извлекаем данные за ВСЕ года из основного массива X_median
    df_all_years = ds_main["X_median"].to_dataframe()

    # Разворачиваем индекс 'Year' в названия колонок
    df_table = df_all_years.unstack(level='Year')
    df_table.columns = df_table.columns.droplevel(0)

    # Надежное преобразование типов данных
    df_table = df_table.fillna(0.0).astype(float).round(2)
    df_table.index.name = "Возраст (лет)"

    # Показываем красивую интерактивную таблицу в Streamlit (здесь индекс отображается нормально)
    st.dataframe(df_table, use_container_width=True)

    # 2. ПОДГОТОВКА ДАННЫХ СПЕЦИАЛЬНО ДЛЯ ЭКСПОРТА В EXCEL
    # Сбрасываем индекс, чтобы "Возраст (лет)" стал полноценной первой числовой колонкой,
    # а в шапке гарантированно остались только чистые года
    df_for_excel = df_table.reset_index()

    # Принудительно превращаем названия колонок-годов в обычные строки, чтобы Excel не путался
    df_for_excel.columns = [str(col) for col in df_for_excel.columns]

    # Экспортируем в CSV с разделителями для русскоязычной локали (точка с запятой и запятая для дробей)
    csv_data = df_for_excel.to_csv(index=False, encoding="utf-8-sig", sep=";", decimal=",")

    st.download_button(
        label="📥 Скачать полную таблицу в CSV (для Excel/Word)",
        data=csv_data,
        file_name=f"age_structure_all_years_{selected_fish}.csv",
        mime="text/csv",
        key="download_csv_all"
    )

