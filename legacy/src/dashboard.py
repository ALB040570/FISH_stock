import streamlit as st
import xarray as xr
import pandas as pd
import plotly.graph_objects as go
import os

fish_dict = {
    "лещ": "lesh",
    "судак": "sudak",
    "окунь": "okun",
    "плотва": "plotva",
    "щука": "shuka",
    "сазан": "sazan",
    "карась": "karas",
    "язь": "yaz"
}

from streamlit import sidebar
from get_yearly_stock_3d import get_yearly_stock_seine_with_ages_on_catch_3d, get_yearly_stock_net_with_ages_on_catch_3d





# ==============================================================================
# 📊 НАСТРОЙКИ СТРАНИЦЫ
# ==============================================================================
st.set_page_config(
    page_title="Байесовский Мониторинг",
    page_icon="🐟",
    layout="wide"
)

st.title("🐟 Байесовский мониторинг и баланс запасов рыб")
st.markdown("---")

DATA_DIR = r"D:\pythonprojects\fish_stock_assesment_1\data_stock"

# ==============================================================================
# 🎛️ ПАНЕЛЬ УПРАВЛЕНИЯ (СЛЕВА)
# ==============================================================================
st.sidebar.header("⚙️ Параметры мониторинга")

waterbody = st.sidebar.selectbox(
    "Выберите водоем:",
    options=["zhaysan", "balkhash", "kapshagai"],
    format_func=lambda x: f"🌊 Водоем: {x.upper()}"
)

fish_species = st.sidebar.selectbox(
    "Выберите вид рыбы:",
    options=["щука", "судак", "лещ", "плотва", "окунь", "сазан", "карась", "язь"],
    format_func=lambda x: f"🐠 {x.capitalize()}"
)

run_version = st.sidebar.selectbox(
    "Версия расчета модели:",
    options=["shuka6", "sudak4", "lesh8", "okun5", "plotva4",
             "sazan5", "karas3", "yaz4"],
    index=1
)


# Шаблон имени файла под вашу архитектуру расчета
file_name = f"{waterbody}_bayes_2g1p_with_ages_3d_{run_version}.nc"
file_path = os.path.join(DATA_DIR, file_name)


# ==============================================================================
# 📥 ЗАГРУЗКА ДАННЫХ
# ==============================================================================
@st.cache_data(show_spinner="Загрузка байесовских метрик из NetCDF...")
def load_fish_data(path):
    if not os.path.exists(path):
        return None
    return xr.open_dataset(path)

yearly_stock_net = get_yearly_stock_net_with_ages_on_catch_3d(waterbody)
yearly_stock_seine = get_yearly_stock_seine_with_ages_on_catch_3d(waterbody)
da_nets = yearly_stock_net.swap_dims({"LessAge": "age"})
da_seine = yearly_stock_seine.swap_dims({"LessAge": "age"})


ds = load_fish_data(file_path)

if ds is None:
    st.warning(f"⚠️ Файл расчета `{file_name}` не найден в директории результатов. {file_path}")
    st.info("Запустите байесовский расчет для этого вида рыбы, чтобы сгенерировать NetCDF куб.")
    st.stop()

# Читаем метаданные из атрибутов датасета
wb_attr = ds.attrs.get("waterbody", waterbody)
model_attr = ds.attrs.get("model_type", "Неизвестная модель")
div_attr = ds.attrs.get("total_divergences", 0)

# Координаты сетки
years = ds.coords['Year'].values
ages = ds.coords['age'].values if 'age' in ds.coords else ds.coords['age_observed'].values
last_year = years[-1]

# ==============================================================================
# 📈 ОСНОВНЫЕ KPI МЕТРИКИ
# ==============================================================================
total_stock_last = float(ds['X_median'].sel(Year=last_year).sum())
mature_stock_last = float(ds['X_median'].sel(Year=last_year, age=slice(3, None)).sum())

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        label=f"Общий запас в {last_year} году (всего штук)",
        value=f"{total_stock_last:,.0f}".replace(",", " ")
    )
with col2:
    st.metric(
        label=f"Ядро популяции (возраст 3+) в {last_year} году",
        value=f"{mature_stock_last:,.0f}".replace(",", " ")
    )
with col3:
    status_color = "🟢" if div_attr == 0 else "🔴"
    st.metric(
        label="Расходимости MCMC (Divergences)",
        value=f"{status_color} {div_attr} шт",
        delta="NUTS градиент" if div_attr == 0 else "Требуется репараметризация",
        delta_color="normal" if div_attr == 0 else "inverse"
    )

st.write(f"**Тип модели:** *{model_attr}*")
st.markdown("---")

# ==============================================================================
# 📊 ГРАФИК 1: ВЕЕРА ДОВЕРИТЕЛЬНЫХ ИНТЕРВАЛОВ ЗАПАСА (ДЛЯ ВЫБРАННОГО ВОЗРАСТА)
# ==============================================================================
st.subheader("📈 Сравнение численности модели и данных двух правдоподобий")

# 1. СНАЧАЛА строим проверенный DataFrame модели (точно такой же, как в таблице)
df_X_model = ds['X_median'].to_pandas()

# На всякий случай убеждаемся, что года — это столбцы.
if df_X_model.index.name == 'Year' or df_X_model.index.max() > 100:
    df_X_model = df_X_model.T

# 2. Формируем список для селектора: добавляем "Все возрасты (Сумма)" в самое начало
age_options = ["Все возрасты (Сумма)"] + list(df_X_model.index)
selected_age = st.selectbox("Выберите возраст для отображения:", options=age_options)

# 3. ГАРАНТИРОВАННЫЙ СИНХРОН: Извлекаем данные в зависимости от выбора
x_vals = df_X_model.columns.values  # строго года [2015, 2016, ..., 2024]

if selected_age == "Все возрасты (Сумма)":
    # Считаем сумму по всем возрастам для каждого года
    y_med = df_X_model.sum(axis=0).values

    # Для доверительного интервала суммируем квантили (оценка неопределенности суммарного запаса)
    df_X_q25 = ds['X_q25'].to_pandas()
    if df_X_q25.index.name == 'Year' or df_X_q25.index.max() > 100: df_X_q25 = df_X_q25.T
    y_q25 = df_X_q25.sum(axis=0).values

    df_X_q75 = ds['X_q75'].to_pandas()
    if df_X_q75.index.name == 'Year' or df_X_q75.index.max() > 100: df_X_q75 = df_X_q75.T
    y_q75 = df_X_q75.sum(axis=0).values
else:
    # Берем строку конкретного выбранного возраста
    y_med = df_X_model.loc[selected_age].values

    df_X_q25 = ds['X_q25'].to_pandas()
    if df_X_q25.index.name == 'Year' or df_X_q25.index.max() > 100: df_X_q25 = df_X_q25.T
    y_q25 = df_X_q25.loc[selected_age].values

    df_X_q75 = ds['X_q75'].to_pandas()
    if df_X_q75.index.name == 'Year' or df_X_q75.index.max() > 100: df_X_q75 = df_X_q75.T
    y_q75 = df_X_q75.loc[selected_age].values

fig_fan = go.Figure()

# Затененный доверительный интервал модели
fig_fan.add_trace(go.Scatter(
    x=list(x_vals) + list(x_vals)[::-1],
    y=list(y_q75) + list(y_q25)[::-1],
    fill='toself',
    fillcolor='rgba(0, 100, 80, 0.15)',
    line=dict(color='rgba(255,255,255,0)'),
    hoverinfo="skip",
    name="Интервал модели (q25-q75)"
))

# Линия медианы модели
fig_fan.add_trace(go.Scatter(
    x=x_vals, y=y_med,
    mode='lines+markers',
    line=dict(color='rgb(0, 100, 80)', width=3),
    marker=dict(size=6),
    name="Медиана модели X"
))

# 4. Первое правдоподобие (Сети)
try:
    if selected_age == "Все возрасты (Сумма)":
        # Суммируем по всей координате возраста для текущей рыбы
        y_nets = da_nets.sel(FishType=fish_species).sum(dim='age').values
    else:
        y_nets = da_nets.sel(FishType=fish_species, age=selected_age).values

    fig_fan.add_trace(go.Scatter(
        x=x_vals, y=y_nets,
        mode='lines+markers',
        line=dict(color='#EF553B', width=2, dash='dash'),
        marker=dict(size=6, symbol='circle'),
        name="Правдоподобие: Сети"
    ))
except Exception as e:
    st.sidebar.caption(f"ℹ️ Нет данных сетей для выбранного режима")

# 5. Второе правдоподобие (Невод)
try:
    if selected_age == "Все возрасты (Сумма)":
        # Суммируем по всей координате возраста для текущей рыбы
        y_seine = da_seine.sel(FishType=fish_species).sum(dim='age').values
    else:
        y_seine = da_seine.sel(FishType=fish_species, age=selected_age).values

    fig_fan.add_trace(go.Scatter(
        x=x_vals, y=y_seine,
        mode='lines+markers',
        line=dict(color='#00CC96', width=2, dash='dot'),
        marker=dict(size=6, symbol='diamond'),
        name="Правдоподобие: Невод"
    ))
except Exception as e:
    st.sidebar.caption(f"ℹ️ Нет данных невода для выбранного режима")

# Настройки отображения
fig_fan.update_layout(
    xaxis_title="Год",
    yaxis_title="Численность / Суммарный запас (штук)",
    hovermode="x unified",
    height=500,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)


st.plotly_chart(fig_fan, width='stretch', key="figure_1")


st.markdown("---")

# ==============================================================================
# 📊 ГРАФИК 2: СТРУКТУРА И ФАКТОРЫ ГИБЕЛИ СТАДА (БЕЗОПАСНОЕ ВЫРАВНИВАНИЕ)
# ==============================================================================
st.subheader("💀 Анализ структуры изъятия и гибели популяции (в штуках)")

# ИСПРАВЛЕНО: Явно берем первый элемент years[0] для min_value
selected_year = st.slider(
    "Выберите год для анализа структуры смертности рыбы:",
    min_value=int(years[0]),
    max_value=int(years[-1]),
    value=int(years[-1])
)

# 1. Извлекаем координаты возрастов для каждой переменной отдельно
age_coords_full = ds["X_median"].coords["age"].values


# 1. Извлекаем координаты возрастов для каждой переменной отдельно, чтобы избежать путаницы
age_coords_full = ds["X_median"].coords["age"].values

# Определяем родные координаты для ПДУ (у него может быть age_observed)
if "age_observed" in ds["pdu_pcs"].dims:
    age_coords_pdu = ds["pdu_pcs"].coords["age_observed"].values
else:
    age_coords_pdu = ds["pdu_pcs"].coords["age"].values

# 2. Создаем отдельные Series со своими индексами возрастов
series_natural = pd.Series(ds["dead_natural_pcs"].sel(Year=selected_year).values, index=age_coords_full)
series_predators = pd.Series(ds["dead_predators_pcs"].sel(Year=selected_year).values, index=age_coords_full)
series_brac = pd.Series(ds["dead_brac_pcs"].sel(Year=selected_year).values, index=age_coords_full)
series_pdu = pd.Series(ds["pdu_pcs"].sel(Year=selected_year).values, index=age_coords_pdu)

# 3. Собираем финальный DataFrame.
# Pandas автоматически выровняет их по индексам возрастов, а отсутствующие (например, 1-й возраст для ПДУ) заполнит 0.0
df_mort = pd.DataFrame({
    "Естественная гибель": series_natural,
    "Выедание хищниками": series_predators,
    "Браконьерский вылов": series_brac,
    "Официальный ПДУ": series_pdu
}, index=ages) # Жестко центрируем по выбранной сетке отображения

df_mort = df_mort.fillna(0.0) # Заменяем NaN на нули для красивого графика

fig_bar = go.Figure()
for col in df_mort.columns:
    fig_bar.add_trace(go.Bar(x=df_mort.index, y=df_mort[col], name=col))



st.plotly_chart(fig_bar, width='stretch', key="figure_2")



st.markdown("---")

# ==============================================================================
# 📋 ТАБЛИЦЫ ДАННЫХ И ТЕХНИЧЕСКИЙ АУДИТRHAT
# ==============================================================================
tab_table, tab_rhat = st.tabs(["📋 Матрица численности (Медианы)", "🛡️ Диагностика сходимости цепей (Rhat)"])

with tab_table:
    st.write(f"### Сводная matrix численности {fish_species} (штук)")
    df_X = ds['X_median'].to_pandas()
    st.dataframe(df_X.style.format("{:,.0f}").background_gradient(cmap="Blues", axis=1))

with tab_rhat:
    # ИСПРАВЛЕНО: Добавлен префикс r'' для сырых строк, чтобы не ломался LaTeX
    st.write(r"### Оценка сходимости цепей (Метрики Гельмана-Рубина \(\widehat{R}\))")
    st.markdown(
        r"Показатель \(\widehat{R} \le 1.05\) гарантирует математическую точность расчетов и перемешивание цепей MCMC.")

    max_rhat_x = float(ds["rhat_X"].max())
    max_rhat_beta = float(ds["rhat_beta"].max())
    max_rhat_q = float(ds["rhat_q_bias"].max())

    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1:
        st.metric(
            label="Макс. Rhat (Численность X)",
            value=f"{max_rhat_x:.3f}",
            delta="Идеально" if max_rhat_x <= 1.05 else "Не сошлось!",
            delta_color="normal" if max_rhat_x <= 1.05 else "inverse"
        )
    with col_r2:
        st.metric(
            label="Макс. Rhat (Промысел Beta)",
            value=f"{max_rhat_beta:.3f}",
            delta="Идеально" if max_rhat_beta <= 1.05 else "Разлет цепей",
            delta_color="normal" if max_rhat_beta <= 1.05 else "inverse"
        )
    with col_r3:
        st.metric(
            label="Макс. Rhat (Уловимость q_bias)",
            value=f"{max_rhat_q:.3f}",
            delta="Идеально" if max_rhat_q <= 1.05 else "Шум съемок",
            delta_color="normal" if max_rhat_q <= 1.05 else "inverse"
        )

    if max_rhat_x > 1.05:
        st.error(
            "⚠️ Внимание! Для некоторых возрастов цепи MCMC застряли в локальных минимумах. Финальные медианы могут быть смещены.")
    else:
        st.success("🎉 Все марковские цепи успешно сошлись к единому биологическому минимуму!")
