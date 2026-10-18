import os
from pathlib import Path
import streamlit as st
import xarray as xr
import numpy as np
import plotly.graph_objects as go

# 1. Справочники соответствия видов рыб и файлов результатов байесовской модели
fish_species = {
    "bream": "lesh8", "zander": "sudak4", "perch": "okun5", "roach": "plotva4",
    "pike": "shuka6", "carp": "sazan5", "crucian carp": "karas28", "ide": "yaz5"
}
fishes = [
    "bream", "zander", "perch", "roach",
    "pike", "carp", "crucian carp", "ide"
]


fishes_dict = {
    "bream": "лещ", "zander": "судак", "perch": "окунь", "roach": "плотва",
    "pike": "щука", "carp": "сазан", "crucian carp": "карась", "ide": "язь"
}


# Инициализация путей к проекту
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data_stock"

st.set_page_config(page_title="Анализ запасов по видам рыб", layout="wide")
st.title("🐟 Сравнительный анализ методов оценки запасов рыб (Жайсан)")
st.markdown("Все графики переведены в относительную динамику (база нормирования — суммарный запас `X_median` по всем возрастам в 2015 году = 1.0).")

# 2. Функция безопасной загрузки NetCDF
@st.cache_data(show_spinner=False)
def load_netcdf(file_name):
    path = DATA_DIR / file_name
    if not path.exists():
        return None
    try:
        with xr.open_dataarray(path) as ds:
            ds.load()
            return ds
    except Exception as e:
        st.error(f"Ошибка чтения файла {file_name}: {e}")
        return None

@st.cache_data(show_spinner=False)
def load_netcdf_main(file_name):
    path = DATA_DIR / file_name
    if not path.exists():
        return None
    try:
        with xr.open_dataset(path) as ds:
            ds.load()
            return ds
    except Exception as e:
        st.error(f"Ошибка чтения файла {file_name}: {e}")
        return None

# Глобальная загрузка внешних массивов правдоподобия
ds_net = load_netcdf("zhaysan_yearly_stock_net_with_ages_on_catch_3d.nc")       # Метод площадей
ds_seine = load_netcdf("zhaysan_yearly_stock_seine_with_ages_on_catch_3d.nc")   # Балансовый метод
ds_net = ds_net.swap_dims({'LessAge': 'age'})
ds_seine = ds_seine.swap_dims({'LessAge': 'age'})

# 3. Выбор вида рыбы в интерфейсе
selected_fish = st.radio("Выберите вид рыбы для анализа:", fishes, horizontal=True)

# Загружаем основной файл результатов байесовской модели для выбранной рыбы
file_code = fish_species[selected_fish]
main_file_name = f"zhaysan_bayes_2g1p_with_ages_3d_{file_code}.nc"

# Загружаем основной файл результатов для выбранной рыбы
ds_main = load_netcdf_main(main_file_name)

if ds_main is None:
    st.error(f"❌ Не удалось загрузить файл результатов `{file_code}.nc` для вида: {selected_fish}")
    st.stop()

# 4. ПОДГОТОВКА И СТРОГОЕ НОРМИРОВАНИЕ ДАННЫХ ВРЕМЕННЫХ РЯДОВ
# Временная ось (Годы)
years = ds_main.coords["Year"].values
# БАЗА НОРМИРОВАНИЯ: Значение X_median в нулевом (2015) году
# base_x_2015 = float(ds_main["X_median"].values[0])
# Безопасное извлечение базового значения 2015 года

total_stock_by_years = ds_main["X_median"].sum(dim="age").values
base_x_2015 = float(total_stock_by_years[0])
if base_x_2015 == 0:
    base_x_2015 = 1.0

# Метрика 1: Общая численность рыбы (уже нормированная)
total_stock_med = total_stock_by_years / base_x_2015

# Обрабатываем квантили общей численности (они тоже двумерные [Year, age])
if "X_q25" in ds_main and "X_q75" in ds_main:
    total_stock_q25 = ds_main["X_q25"].sum(dim='age').values / base_x_2015
    total_stock_q75 = ds_main["X_q75"].sum(dim='age').values / base_x_2015
else:
    total_stock_q25, total_stock_q75 = None, None

# Метрика 2: Численность без мальков (Исключаем первый индекс возраста 0, берем срез с 1)
no_infants_stock = ds_main["X_median"].isel({'age': slice(1, None)}).sum(dim='age').values / base_x_2015

# Метрика 3: Оценка методом площадей (из внешнего файла сетей zhaysan_stock_net)
fish_type = fishes_dict[selected_fish]
if ds_net is not None and fish_type in ds_net.coords.get("FishType", []):
    area_method_raw = ds_seine.sel(FishType=fish_type).sum(dim="age").values

    area_method_relative = area_method_raw / base_x_2015
else:
    area_method_relative = np.zeros(len(years))

# Метрика 4: Оценка балансовым методом (из внешнего файла неводов zhaysan_stock_seine)
if ds_seine is not None and fish_type in ds_seine.coords.get("FishType", []):
    balance_method_raw = ds_net.sel(FishType=fish_type).sum(dim="age").values
    balance_method_relative = balance_method_raw / base_x_2015
else:
    balance_method_relative = np.zeros(len(years))

# 5. ПОСТРОЕНИЕ И ОФОРМЛЕНИЕ ГРАФИКА ДЛЯ НАУЧНОЙ СТАТЬИ
fig = go.Figure()

# А. Затененный веер доверительного интервала модели (95% ДИ)
if total_stock_q25 is not None and total_stock_q75 is not None:
    fig.add_trace(go.Scatter(x=years, y=total_stock_q75, mode='lines', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(
        x=years, y=total_stock_q25, mode='lines', line=dict(width=0),
        fill='tonexty', fillcolor='rgba(52, 152, 219, 0.10)',
        name='95% доверительный интервал байесовской модели', showlegend=True
    ))

# Б. Линия 1: Общая численность
fig.add_trace(go.Scatter(
    x=years, y=total_stock_med, mode='lines+markers',
    line=dict(color='#2980b9', width=3), name='Общая численность (Модель, все возраста)'
))

# В. Линия 2: Численность без мальков (Старше 1 года)
fig.add_trace(go.Scatter(
    x=years, y=no_infants_stock, mode='lines+markers',
    line=dict(color='#27ae60', width=2.5, dash='dash'), name='Численность старше 1 года (Без мальков)'
))

# Г. Линия 3: Оценка методом площадей (независимые данные сетей)
fig.add_trace(go.Scatter(
    x=years, y=area_method_relative, mode='lines+markers',
    line=dict(color='#e67e22', width=2), name='Оценка методом площадей (Правдоподобие сетей)'
))

# Д. Линия 4: Оценка балансовым методом (независимые данные неводов)
fig.add_trace(go.Scatter(
    x=years, y=balance_method_relative, mode='lines+markers',
    line=dict(color='#9b59b6', width=2), name='Оценка балансовым методом (Правдоподобие неводов)'
))

# Е. Справочная горизонтальная линия базового 2015 года (уровень 1.0)
fig.add_shape(
    type="line", x0=years[0], y0=1.0, x1=years[-1], y1=1.0,
    line=dict(color="rgba(127, 140, 141, 0.5)", width=1.5, dash="dot")
)

# Оформление графика в академическом стиле Plotly
fig.update_layout(
    title=dict(
        text=f"Рис. Относительная динамика запасов и верификация методов оценки для вида: {selected_fish.upper()}",
        font=dict(size=14, color="black")
    ),
    xaxis=dict(title="Календарный год", tickmode="array", tickvals=years, gridcolor="rgba(240,240,240,1)"),
    yaxis=dict(title="Индекс численности запаса (Доля от уровня 2015 г.)", gridcolor="rgba(240,240,240,1)"),
    template="plotly_white",
    hovermode="x unified",
    height=600,
    width=1100,
    legend=dict(
        orientation="h",
        yanchor="bottom", y=-0.28,
        xanchor="center", x=0.5,
        font=dict(size=11)
    )
)

st.plotly_chart(fig, use_container_width=True)

# 6. ВЫВОД КЛЮЧЕВЫХ ТРЕНДОВ В ВИДЕ ТАБЛИЦЫ ДЛЯ ВСТАВКИ В СТАТЬЮ
st.subheader("📊 Сводные результаты относительной динамики популяции")
df_trends = xr.Dataset({
    "Общая численность (Модель)": (["Год"], np.round(total_stock_med, 3)),
    "Старше 1 года (Без мальков)": (["Год"], np.round(no_infants_stock, 3)),
    "Метод площадей (Сети)": (["Год"], np.round(area_method_relative, 3)),
    "Балансовый метод (Невода)": (["Год"], np.round(balance_method_relative, 3))
}, coords={"Год": years}).to_dataframe()

st.dataframe(df_trends, use_container_width=True)
st.info("📸 **Памятка для экспорта данных:** Кликните на иконку фотоаппарата на графике Plotly, чтобы скачать рисунок высокого разрешения в формате `.png`. Таблицу ниже можно выделить мышкой и напрямую скопировать в Word-файл вашей статьи.")
