import os
from pathlib import Path
import streamlit as st
import xarray as xr
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

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

st.set_page_config(page_title="Комплексный байесовский аудит", layout="wide")
st.title("📊 Комплексный байесовский анализ и верификация запасов рыб (Жайсан)")
st.markdown("Инструмент аудита эколого-промысловых параметров, выявления перелова и браконьерства.")


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


# Загрузка внешних 3D массивов правдоподобия с приведением координат
ds_net = load_netcdf("zhaysan_yearly_stock_net_with_ages_on_catch_3d.nc")       # Метод площадей
ds_seine = load_netcdf("zhaysan_yearly_stock_seine_with_ages_on_catch_3d.nc")   # Балансовый метод
ds_net = ds_net.swap_dims({'LessAge': 'age'})
ds_seine = ds_seine.swap_dims({'LessAge': 'age'})

# Находим имя переменной внутри 3D куба (обычно первая переменная данных)
# var_net = list(ds_net.data_vars)[0] if ds_net is not None else None
# var_seine = list(ds_seine.data_vars)[0] if ds_seine is not None else None

# 3. Выбор вида рыбы в интерфейсе
selected_fish = st.radio(
    "Выберете вид рыбы для анализа:",
    fishes,
    horizontal=True
)


file_code = fish_species[selected_fish]
main_file_name = f"zhaysan_bayes_2g1p_with_ages_3d_{file_code}.nc"

# Загружаем основной файл результатов для выбранной рыбы
ds_main = load_netcdf_main(main_file_name)

if ds_main is None:
    st.error(f"❌ Не удалось загрузить файл результатов `{file_code}.nc` для вида: {selected_fish}")
    st.stop()

# 4. РАСЧЕТ СКВОЗНОЙ БАЗЫ НОРМИРОВАНИЯ (Знаменатель)
years = ds_main.coords["Year"].values
ages = ds_main.coords["age"].values

# Суммарный медианный запас модели по ВСЕМ возрастам в базовом 2015 году
total_stock_2015_absolute = float(ds_main["X_median"].isel(Year=0).sum(dim="age").values)
if total_stock_2015_absolute == 0:
    total_stock_2015_absolute = 1.0

# 5. СОЗДАНИЕ ИНТЕРФЕЙСА ВКЛАДОК
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Динамика и Верификация",
    "🏹 Промысел и Браконьерство (β)",
    "⚰️ Естественная смертность (s)",
    "🚨 Повозрастной Аудит (Графики)",
    "📋 Табличный повозрастной аудит (Для статьи)"
])

# ==============================================================================
# ВКЛАДКА 1: ОТНОСИТЕЛЬНАЯ ЧИСЛЕННОСТЬ И ВЕРИФИКАЦИЯ МЕТОДИК
# ==============================================================================
with tab1:
    st.subheader("Сравнение траекторий относительной численности")

    total_stock_absolute = ds_main["X_median"].sum(dim="age").values
    no_infants_absolute = ds_main["X_median"].isel(age=slice(1, None)).sum(dim="age").values

    total_stock_relative = total_stock_absolute / total_stock_2015_absolute
    no_infants_relative = no_infants_absolute / total_stock_2015_absolute

    fish_type = fishes_dict[selected_fish]

    # Метод площадей (Сети 3D)
    if ds_net is not None: # and selected_fish in ds_net.coords.get("FishType", []):
        balance_method_raw = ds_net.sel(FishType=fish_type).sum(dim="age").values
        balance_method_relative = balance_method_raw / total_stock_2015_absolute
    else:
        balance_method_relative = np.zeros(len(years))

    # Балансовый метод (Невода 3D)
    if ds_seine is not None: # and selected_fish in ds_seine.coords.get("FishType", []):
        area_method_raw = ds_seine.sel(FishType=fish_type).sum(dim="age").values
        area_method_relative = area_method_raw / total_stock_2015_absolute
    else:
        area_method_relative = np.zeros(len(years))

    # 4. Извлечение и нормирование суммарного ПДУ для текущей рыбы
    if "pdu_pcs" in ds_main or "PDU" in ds_main:
        total_pdu_absolute = ds_main["pdu_pcs"].sum(dim="age_observed").values
        total_pdu_relative = total_pdu_absolute / total_stock_2015_absolute
    else:
        total_pdu_relative = np.zeros(len(years))


    fig1 = go.Figure()

    # Модель: Общая численность
    fig1.add_trace(go.Scatter(
        x=years, y=total_stock_relative, mode='lines+markers',
        name='Байесовская модель: Общий запас',
        line=dict(color='#2980b9', width=3.5)
    ))

    # Модель: Без мальков
    fig1.add_trace(go.Scatter(
        x=years, y=no_infants_relative, mode='lines+markers',
        name='Байесовская модель: Старше 1 года (Без мальков)',
        line=dict(color='#27ae60', width=2.5, dash='dash')
    ))

    # Метод площадей
    fig1.add_trace(go.Scatter(
        x=years, y=area_method_relative, mode='lines+markers',
        name='Метод площадей (Учетные уловы, сети)',
        line=dict(color='#e67e22', width=2)
    ))

    # Балансовый метод
    fig1.add_trace(go.Scatter(
        x=years, y=balance_method_relative, mode='lines+markers',
        name='Балансовый метод (Учетные уловы, невода)',
        line=dict(color='#9b59b6', width=2)
    ))

    # ОБЪЕДИНЕНИЕ: Добавляем линию назначенного чиновниками ПДУ
    fig1.add_trace(go.Scatter(
        x=years, y=total_pdu_relative, mode='lines+markers',
        name='Официально назначенная квота ПДУ',
        line=dict(color='#e74c3c', width=3, dash='dot'),
        marker=dict(symbol='square', size=7)
    ))

    # Горизонтальная справочная линия базового уровня 2015 года
    fig1.add_shape(
        type="line", x0=years[0], y0=1.0, x1=years[-1], y1=1.0,
        line=dict(color="rgba(127, 140, 141, 0.4)", width=1.5, dash="dot")
    )

    # Академическое оформление графика
    fig1.update_layout(
        title=dict(
            text=f"Рис. Интегральная относительная динамика запасов, квот ПДУ и верификация методов для вида: {selected_fish.upper()}",
            font=dict(size=14, color="black")
        ),
        xaxis=dict(title="Календарный год", tickmode="array", tickvals=years, gridcolor="rgba(240,240,240,1)"),
        yaxis=dict(title="Индекс (Доля от суммарного запаса модели в 2015 г.)", gridcolor="rgba(240,240,240,1)"),
        template="plotly_white",
        hovermode="x unified",
        height=620,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.25,
            xanchor="center", x=0.5,
            font=dict(size=11)
        )
    )

    st.plotly_chart(fig1, width='stretch')

# ==============================================================================
# ВКЛАДКА 2: КОЭФФИЦИЕНТ БРАКОНЬЕРСТВА (beta)
# ==============================================================================
with tab2:
    st.subheader("Динамика годового коэффициента отклонения улова / браконьерства (β)")
    if "beta_median" in ds_main or "beta" in ds_main:
        beta_var = "beta_median" if "beta_median" in ds_main else "beta"
        # Возьмем среднее по возрастам для отображения чистого годового тренда
        beta_years = ds_main[beta_var].mean(dim="age").values if "age" in ds_main[beta_var].dims else ds_main[
            beta_var].values

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=years, y=beta_years, mode='lines+markers', name='Коэффициент β (Медиана)',
                                  line=dict(color='#c0392b', width=3)))
        fig2.add_shape(type="line", x0=years[0], y0=1.0, x1=years[-1], y1=1.0, line=dict(color="grey", dash="dash"),
                       name="Базовый уровень (ПДУ = Улов)")
        fig2.update_layout(template="plotly_white", xaxis_title="Год", yaxis_title="Значение коэффициента β",
                           title="Увеличение β > 1.0 показывает масштаб скрытого недоучета / браконьерства")
        st.plotly_chart(fig2, width='stretch')
    else:
        st.warning("Переменная `beta` не найдена в файле результатов.")

# ==============================================================================
# ВКЛАДКА 3: ЕСТЕСТВЕННАЯ СМЕРТНОСТЬ (s)
# ==============================================================================
with tab3:
    st.subheader("Повозрастная парабола естественной смертности (s)")
    if "s" in ds_main or "s_median" in ds_main:
        s_var = "s_median" if "s_median" in ds_main else "s"
        # Построим тепловую карту (Heatmap) повозрастной смертности по годам
        s_data = ds_main[s_var].values

        fig3 = px.imshow(
            s_data, labels=dict(x="Возраст (Age)", y="Календарный год", color="Смертность s"),
            x=ages, y=years, color_continuous_scale="Reds", aspect="auto"
        )
        fig3.update_layout(title="Распределение естественной смертности s по возрастам и годам")
        st.plotly_chart(fig3, width='stretch')
    else:
        st.warning("Переменная смертности `s` не найдена в файле результатов.")

# ==============================================================================
# ВКЛАДКА 4:🚨 ПДУ И ЗАПАС, НОРМИРОВАННЫЕ НА ПОВОЗРАСТНОЙ ЗАПАС 2015 ГОДА
# ==============================================================================
with tab4:
    st.subheader("🚨 Повозрастной аудит перелова (База нормирования — запас конкретного возраста в 2015 г.)")
    st.markdown(
        "Каждый возраст нормирован на самого себя в базовом 2015 году. Уровень **1.0** — это исходное здоровое состояние популяции. "
        "Красный столбик показывает, какую долю от первоначального запаса этого возраста составляет квота ПДУ. "
        "Если красный столбик (ПДУ) выше синего (Текущий запас) — квота физически превышает количество оставшейся в озере рыбы.")

    if "pdu_pcs" in ds_main:
        pdu_var = "pdu_pcs" if "pdu_pcs" in ds_main else "PDU"

        # 1. Извлекаем 2D матрицы исходных абсолютных значений (10 лет х 16 возрастов)
        pdu_matrix = ds_main[pdu_var].values
        x_matrix = ds_main["X_median"].values

        # 2. Вытаскиваем вектор запаса по возрастам в базовом 2015 году (строка с индексом 0)
        # Добавляем 1e-6 для защиты от деления на ноль, если какие-то старшие возраста в 2015 году были пустыми
        stock_base_2015_by_age = x_matrix[0, :] + 1e-6

        # 3. Интерактивный слайдер выбора календарного года для детализации
        selected_year = st.select_slider("Выберите календарный год для повозрастного аудита квот:", options=years,
                                         key="year_slider_tab4")
        year_idx = int(np.where(years == selected_year)[0][0])

        # 4. СТРОГОЕ ПОВОЗРАСТНОЕ ДЕЛЕНИЕ НА БАЗУ 2015 ГОДА
        # Делим векторы текущего выбранного года (1D массивы) поэлементно на вектор 2015 года
        pdu_at_year_relative = pdu_matrix[year_idx, :] / stock_base_2015_by_age[1:]
        stock_at_year_relative = x_matrix[year_idx, :] / stock_base_2015_by_age

        # 5. СТРОИТЕЛЬСТВО СРАВНИТЕЛЬНОЙ ДИАГРАММЫ PLOTLY
        fig4 = go.Figure()

        # Фактический остаток запаса в текущем году (Доля от нормы 2015 г.)
        fig4.add_trace(go.Bar(
            x=ages, y=stock_at_year_relative,
            name=f'Остаток запаса в {selected_year} г. (в долях от 2015 г.)',
            marker_color='#2980b9', opacity=0.85
        ))

        # Официальный лимит ПДУ в текущем году (В долях от нормы 2015 г.)
        fig4.add_trace(go.Bar(
            x=ages, y=pdu_at_year_relative,
            name=f'Назначенный ПДУ в {selected_year} г. (в долях от запаса 2015 г.)',
            marker_color='#e74c3c', opacity=0.90
        ))

        # Справочная горизонтальная линия "Линии горизонта" (уровень 1.0 — состояние 2015 года)
        fig4.add_shape(
            type="line", x0=ages[0], y0=1.0, x1=ages[-1], y1=1.0,
            line=dict(color="rgba(44, 62, 80, 0.6)", width=2, dash="dash")
        )

        fig4.update_layout(
            barmode='group', template="plotly_white",
            xaxis=dict(title="Возраст рыбы (age)", tickmode="array", tickvals=ages),
            yaxis=dict(title="Индекс объема когорты (Доля от уровня этого же возраста в 2015 г.)",
                       gridcolor="rgba(240,240,240,1)"),
            title=dict(
                text=f"Рис. Повозрастной аудит истощения запаса и избыточности квот ПДУ в {selected_year} году для вида: {selected_fish.upper()}",
                font=dict(size=14)
            ),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig4, width='stretch')

        # 6. АВТОМАТИЧЕСКИЙ АНАЛИЗ ПРЕВЫШЕНИЯ КВОТ НАД ТЕКУЩИМ ЗАПАСОМ
        # Находим возраста, где ПДУ текущего года превысил реальное наличие рыбы текущего года
        overfishing_mask = pdu_matrix[year_idx, :] > x_matrix[year_idx, 1:]
        ages1 = ages[1:]
        overfishing_ages = ages1[overfishing_mask]

        if len(overfishing_ages) > 0:
            st.error(
                f"🚨 **ОБНАРУЖЕН БИОЛОГИЧЕСКИЙ ТУПИК ПРЕМЫСЛА!** В {selected_year} году официально назначенные лимиты ПДУ "
                f"физически превысили объём доступной живой рыбы в водоеме для возрастов: {list(overfishing_ages)}. "
                f"Модель зафиксировала численный перелов.")

            # Дополнительное текстовое пояснение для пользователя дашборда
            st.markdown(
                f"**Научный комментарий:** Превышение квот над остатком популяции для средних и старших возрастов доказывает, "
                f"что промысловые квоты {selected_year} года формировались без учета реального когортного истощения стада {selected_fish}. "
                f"Это привело к искусственному 'выжиганию' репродуктивного ядра популяции.")
        else:
            st.success(
                f"✅ В {selected_year} году официальные лимиты ПДУ формально не превышали текущую численность доступных когорт.")
    else:
        st.warning("Переменная ПДУ или X_median не обнаружена в структуре NetCDF файла.")

    # ==============================================================================
    # ИНТЕГРАЛЬНЫЙ АУДИТ: СУММАРНЫЙ ПДУ VS СУММАРНЫЙ ЗАПАС ПО ГОДАМ
    # ==============================================================================
    st.markdown("---")
    st.subheader("📈 Интегральный аудит: Динамика суммарного ПДУ и суммарного Запаса")
    st.markdown(
        "Эти графики показывают глобальный баланс между промысловым изъятием и численностью популяции за все 10 лет.")

    # Расчет суммарных годовых рядов (схлопываем ось возрастов 'age')
    total_pdu_by_years = pdu_matrix.sum(axis=1)  # Сумма ПДУ по годам в штуках
    total_stock_by_years = x_matrix.sum(axis=1)  # Сумма Запаса по годам в штуках

    # База нормирования 2015 года (сумма по возрастам в первый год)
    base_stock_2015 = total_stock_by_years[0]

    # Перевод в относительные индексы
    total_pdu_relative = total_pdu_by_years / base_stock_2015
    total_stock_relative = total_stock_by_years / base_stock_2015

    # Создаем две колонки для отображения графиков бок о бок
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Абсолютные значения (в штуках рыбы)**")
        fig_abs = go.Figure()

        # Линия суммарного запаса
        fig_abs.add_trace(go.Scatter(
            x=years, y=total_stock_by_years, mode='lines+markers',
            name='Суммарный запас (все возраста)',
            line=dict(color='#2980b9', width=4),
            marker=dict(size=8)
        ))

        # Линия назначенного ПДУ
        fig_abs.add_trace(go.Scatter(
            x=years, y=total_pdu_by_years, mode='lines+markers',
            name='Назначенный ПДУ (все возраста)',
            line=dict(color='#e74c3c', width=3, dash='dash'),
            marker=dict(size=8)
        ))

        fig_abs.update_layout(
            template="plotly_white",
            xaxis=dict(title="Календарный год", tickmode="array", tickvals=years),
            yaxis=dict(title="Численность (в штуках)", gridcolor="rgba(240,240,240,1)"),
            hovermode="x unified",
            legend=dict(orientation="h", y=-0.2)
        )
        st.plotly_chart(fig_abs, use_container_width=True)

    with col2:
        st.markdown("**Относительные индексы (Доля от уровня 2015 года = 1.0)**")
        fig_rel = go.Figure()

        # Линия относительного запаса
        fig_rel.add_trace(go.Scatter(
            x=years, y=total_stock_relative, mode='lines+markers',
            name='Индекс Запаса',
            line=dict(color='#27ae60', width=4),
            marker=dict(size=8)
        ))

        # Линия относительного ПДУ
        fig_rel.add_trace(go.Scatter(
            x=years, y=total_pdu_relative, mode='lines+markers',
            name='Индекс ПДУ',
            line=dict(color='#c0392b', width=3, dash='dash'),
            marker=dict(size=8)
        ))

        # Линия горизонта (уровень 2015 года)
        fig_rel.add_shape(
            type="line", x0=years[0], y0=1.0, x1=years[-1], y1=1.0,
            line=dict(color="rgba(127, 140, 141, 0.5)", width=1.5, dash="dot")
        )

        fig_rel.update_layout(
            template="plotly_white",
            xaxis=dict(title="Календарный год", tickmode="array", tickvals=years),
            yaxis=dict(title="Индекс (Доля от запаса 2015 г.)", gridcolor="rgba(240,240,240,1)"),
            hovermode="x unified",
            legend=dict(orientation="h", y=-0.2)
        )
        st.plotly_chart(fig_rel, use_container_width=True)

    # Аналитическая справка под графиками
    st.markdown("**📊 Экспресс-интерпретация интегральных графиков для статьи:**")

    # Находим критический год перелома, когда ПДУ в абсолютах приблизился к запасу или превысил его
    danger_years = years[total_pdu_by_years > total_stock_by_years]

    if len(danger_years) > 0:
        st.warning(f"⚠️ **Критическая фаза перепромысла:** В период {list(danger_years)} суммарная назначенная "
                   f"квота ПДУ физически превысила общую численность всей популяции {selected_fish} в водоеме. "
                   f"Это математически доказывает факт административного уничтожения запаса.")
    else:
        # Находим годы, где квота составляла опасный процент от популяции (например, более 30%)
        high_pressure_years = years[(total_pdu_by_years / (total_stock_by_years + 1e-6)) > 0.3]
        if len(high_pressure_years) > 0:
            st.info(f"💡 **Зона высокого промыслового давления:** В годы {list(high_pressure_years)} суммарный ПДУ "
                    f"составлял более 30% от всей численности стада. В условиях естественной смертности "
                    f"такое изъятие спровоцировало демографический спад популяции.")

# ==============================================================================
# ВКЛАДКА 5: 📋 ТАБЛИЧНЫЙ ПОВОЗРАСТНОЙ АУДИТ (ГЕНЕРАТОР ТАБЛИЦ ДЛЯ СТАТЬИ)
# ==============================================================================
with tab5:
    st.subheader(f"📋 Повозрастная матрица индексов Запаса и ПДУ для вида: {selected_fish.upper()}")
    st.markdown(
        "Таблица содержит точные расчетные индексы (нормированные поэлементно на уровень соответствующего возраста в 2015 году). "
        "Ячейки, где **ПДУ текущего года превысил фактическое наличие рыбы**, автоматически подсвечиваются **красным цветом**.")

    if "pdu_pcs" in ds_main or "PDU" in ds_main:
        pdu_matrix = ds_main['pdu_pcs'].values
        x_matrix = ds_main["X_median"].values
        stock_base_2015_by_age = x_matrix[0, :] + 1e-6



        # Строим сводную таблицу в формате Pandas DataFrame
        rows = []
        for yr_idx, yr in enumerate(years):
            for age_idx, age in enumerate(ages1):
                # Пропускаем возраста, где ПДУ равен нулю изначально (молодь, не ловится)
                if pdu_matrix[yr_idx, age_idx] == 0 and yr_idx > 0:
                    continue

                rel_stock = x_matrix[yr_idx, age_idx] / stock_base_2015_by_age[age_idx]
                rel_pdu = pdu_matrix[yr_idx, age_idx] / stock_base_2015_by_age[age_idx]

                # Фиксируем признак перелова в абсолютных штуках
                is_overfished = pdu_matrix[yr_idx, age_idx] > x_matrix[yr_idx, age_idx]

                if is_overfished:
                    rows.append({
                        "Календарный год": int(yr),
                        "Возраст (age)": int(age),
                        "Индекс Запаса": round(rel_stock, 3),
                        "Индекс ПДУ": round(rel_pdu, 3),
                        # "Перелов (Абсолютный)": "🚨 КРИТИЧЕСКИЙ" if is_overfished else "✅ Норма"
                    })

        df_audit = pd.DataFrame(rows)
        print('df_audit = ', df_audit)


        # Функция стилизации: если обнаружен критический перелов, красим всю строку в красный
        # def highlight_overfishing(row):
        #     if row["Перелов (Абсолютный)"] == "🚨 КРИТИЧЕСКИЙ":
        #         return ['background-color: rgba(231, 76, 60, 0.25); color: #c0392b; font-weight: bold'] * len(row)
        #     return [''] * len(row)


        # Применяем стили и выводим таблицу
        # styled_df = df_audit.style.apply(highlight_overfishing, axis=1)
        # st.dataframe(styled_df, use_container_width=True, height=600)
        st.dataframe(df_audit, width='stretch', height=600)

        st.success(
            "💡 **Инструкция для публикации:** Выделите нужные строки таблицы мышкой, скопируйте (`Ctrl+C`) и вставьте в Word. Матрица полностью сформирована под формат академических журналов.")
    else:
        st.warning("Переменные ПДУ или X_median не найдены.")
