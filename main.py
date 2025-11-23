import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import re
from datetime import datetime
import numpy as np

st.set_page_config(
    page_title="Дашборд по складу",
    layout="wide",
    page_icon="📦"
)

# ==================== СТИЛИ ======================
st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        padding-top: 20px;
    }
    .kpi-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        text-align: center;
        margin-bottom: 10px;
    }
    .kpi-value {
        font-size: 28px;
        font-weight: 700;
        color: #2c3e50;
    }
    .kpi-label {
        font-size: 16px;
        color: #6c757d;
    }
    .info-card {
        background-color: #e8f4fd;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid #1890ff;
    }
    .tree-node {
        margin-left: 15px;
        padding: 5px 0;
    }
    .shift-analysis-card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    .anomaly-card {
        background-color: #fff5f5;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #e53e3e;
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

# ==================== САЙДБАР ======================
st.sidebar.title("📊 Навигация")
page = st.sidebar.radio(
    "Раздел:",
    ["Главная", "Динамика", "Анализ по сменам", "Аномалии", "Инструкция"]
)

uploaded_file = st.sidebar.file_uploader("📤 Загрузите Excel-файл", type=["xlsx"])

# ==================== ФУНКЦИИ ======================
def normalize_time_str(time_str):
    """Приводит формат времени к виду 6:00-18:00 / 18:00-6:00"""
    if pd.isna(time_str):
        return None
    
    s = str(time_str).strip()
    
    # Если уже в правильном формате, возвращаем как есть
    if s in ["6:00-18:00", "18:00-6:00"]:
        return s
    
    # Заменяем различные типы дефисов и убираем пробелы
    s = s.replace("–", "-").replace("—", "-").replace(" ", "")
    s = s.replace(".", ":")
    
    # Извлекаем числа из строки
    numbers = re.findall(r'\d+', s)
    
    if len(numbers) >= 2:
        first_num = int(numbers[0])
        second_num = int(numbers[1])
        
        # Определяем формат на основе первого числа
        if first_num == 6:
            return "6:00-18:00"
        elif first_num == 18:
            return "18:00-6:00"
    
    # Если не удалось определить, возвращаем исходное значение
    return s

def process_merged_cells(df):
    """Обрабатывает объединенные ячейки в столбце Дата"""
    df_processed = df.copy()
    
    # Заполняем пропущенные даты предыдущими значениями
    df_processed["Дата"] = df_processed["Дата"].ffill()
    
    return df_processed

def process_shift_numbers(df):
    """Обрабатывает номера смен: преобразует буквы в цифры и удаляет строки с None"""
    df_processed = df.copy()
    
    # Создаем словарь для преобразования букв в цифры
    shift_mapping = {
        'А': '1', 'A': '1',  # Кириллическая и латинская A
        'Б': '2', 'B': '2',  # Кириллическая Б и латинская B
        'В': '3', 'C': '3',  # Кириллическая В и латинская C
        'Г': '4', 'D': '4',  # Кириллическая Г и латинская D
    }
    
    # Функция для преобразования одного значения
    def convert_shift(value):
        if pd.isna(value) or value is None or value == '':
            return None
        
        value_str = str(value).strip().upper()
        
        # Если значение уже цифра от 1 до 4, оставляем как есть
        if value_str in ['1', '2', '3', '4']:
            return value_str
        
        # Если значение буква, преобразуем по словарю
        if value_str in shift_mapping:
            return shift_mapping[value_str]
        
        # Если значение не распознано, возвращаем None
        return None
    
    # Применяем преобразование к столбцу "№ смены"
    df_processed["№ смены"] = df_processed["№ смены"].apply(convert_shift)
    
    # Удаляем строки, где номер смены None (после преобразования)
    df_processed = df_processed.dropna(subset=["№ смены"])
    
    return df_processed

def create_date_tree(df):
    """Создает дерево дат для фильтрации: Год -> Месяц -> Неделя -> День"""
    unique_dates = df["Дата"].unique()
    
    date_tree = {}
    
    for date in unique_dates:
        year = date.year
        month = date.month
        week = datetime(year, month, date.day).isocalendar()[1]
        day = date.day
        
        if year not in date_tree:
            date_tree[year] = {}
        
        if month not in date_tree[year]:
            date_tree[year][month] = {}
        
        if week not in date_tree[year][month]:
            date_tree[year][month][week] = []
        
        if day not in date_tree[year][month][week]:
            date_tree[year][month][week].append(day)
    
    # Сортируем дни в каждой неделе
    for year in date_tree:
        for month in date_tree[year]:
            for week in date_tree[year][month]:
                date_tree[year][month][week].sort()
    
    return date_tree

def load_excel_separately(uploaded_file):
    """Загружает основные столбцы и подстолбцы отдельно, затем объединяет"""
    try:
        # Загружаем данные с двумя строками заголовков чтобы увидеть структуру
        df_raw = pd.read_excel(uploaded_file, sheet_name="Грузооборот", header=None, nrows=5)
        
        # Ищем строку с основными заголовками (Дата, Время, № смены)
        header_row = None
        for i in range(min(5, len(df_raw))):
            row_values = df_raw.iloc[i].dropna().astype(str).str.strip().tolist()
            if 'Дата' in row_values and 'Время' in row_values and '№ смены' in row_values:
                header_row = i
                break
        
        if header_row is None:
            st.error("Не удалось найти строку с заголовками (Дата, Время, № смены)")
            st.write("Первые 5 строк файла:")
            st.dataframe(df_raw)
            st.stop()
        
        # Загружаем основные данные начиная с найденной строки заголовков
        df_main = pd.read_excel(uploaded_file, sheet_name="Грузооборот", header=header_row)
        
        # Убираем пустые строки и Unnamed колонки
        df_main.dropna(how="all", inplace=True)
        df_main = df_main.loc[:, ~df_main.columns.str.contains("Unnamed", na=False)]
        
        # Теперь загружаем подстолбцы сотрудников
        # Предполагаем, что подстолбцы находятся в следующей строке после заголовков
        employee_header_row = header_row + 1
        
        # Загружаем данные еще раз, начиная со строки подстолбцов
        df_employees_raw = pd.read_excel(uploaded_file, sheet_name="Грузооборот", header=employee_header_row)
        
        # Выбираем только столбцы сотрудников
        employee_columns = [
            'Старший смены', 'Помощник старшего смены', 'Кладовщик', 
            'Водитель погрузчика', 'Рабочий склада', 'Всего сотрудников'
        ]
        
        # Ищем эти столбцы в данных
        employee_data = {}
        for col in employee_columns:
            if col in df_employees_raw.columns:
                employee_data[col] = df_employees_raw[col]
        
        # Если нашли столбцы сотрудников, добавляем их к основным данным
        if employee_data:
            employee_df = pd.DataFrame(employee_data)
            
            # Убеждаемся, что количество строк совпадает
            min_rows = min(len(df_main), len(employee_df))
            df_main = df_main.iloc[:min_rows].copy()
            employee_df = employee_df.iloc[:min_rows].copy()
            
            # Объединяем данные
            for col in employee_columns:
                if col in employee_df.columns:
                    df_main[col] = employee_df[col].values
        
        return df_main
        
    except Exception as e:
        st.error(f"Ошибка при загрузке файла: {e}")
        st.stop()

def detect_anomalies(df, column='Грузооборот всего', threshold=2):
    """Обнаруживает аномалии в данных используя метод стандартных отклонений"""
    if column not in df.columns:
        return pd.DataFrame()
    
    # Вычисляем среднее и стандартное отклонение
    mean_val = df[column].mean()
    std_val = df[column].std()
    
    # Вычисляем верхнюю и нижнюю границы для аномалий
    upper_bound = mean_val + threshold * std_val
    lower_bound = mean_val - threshold * std_val
    
    # Находим аномалии
    anomalies = df[(df[column] > upper_bound) | (df[column] < lower_bound)].copy()
    
    # Добавляем информацию о типе аномалии
    anomalies['Тип аномалии'] = anomalies[column].apply(
        lambda x: 'Высокая' if x > upper_bound else 'Низкая'
    )
    anomalies['Отклонение'] = anomalies[column] - mean_val
    anomalies['Отклонение в σ'] = (anomalies[column] - mean_val) / std_val
    
    return anomalies

def calculate_trend(df, x_col, y_col):
    """Вычисляет линейный тренд для данных с использованием numpy"""
    if len(df) < 2:
        return None, None, None
    
    try:
        # Создаем числовую ось X
        x_numeric = np.arange(len(df))
        y_values = df[y_col].values
        
        # Вычисляем коэффициенты линейной регрессии вручную
        n = len(x_numeric)
        sum_x = np.sum(x_numeric)
        sum_y = np.sum(y_values)
        sum_xy = np.sum(x_numeric * y_values)
        sum_xx = np.sum(x_numeric * x_numeric)
        
        # Вычисляем наклон (slope) и пересечение (intercept)
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
        intercept = (sum_y - slope * sum_x) / n
        
        # Вычисляем линию тренда
        trend_line = slope * x_numeric + intercept
        
        # Вычисляем R² (коэффициент детерминации)
        y_mean = np.mean(y_values)
        ss_tot = np.sum((y_values - y_mean) ** 2)  # общая сумма квадратов
        ss_res = np.sum((y_values - trend_line) ** 2)  # сумма квадратов остатков
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        return trend_line, slope, r_squared
    
    except Exception as e:
        st.error(f"Ошибка при вычислении тренда: {e}")
        return None, None, None

# ==================== ОСНОВНАЯ ЛОГИКА ======================
if uploaded_file:
    # Загружаем и обрабатываем файл
    df = load_excel_separately(uploaded_file)
    
    # Проверяем наличие основных столбцов
    required_columns = ["Дата", "Время", "№ смены"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        st.error(f"Не найдены необходимые столбцы: {missing_columns}")
        st.info("Найденные столбцы:")
        st.write(list(df.columns))
        st.stop()

    # Обрабатываем объединенные ячейки в столбце Дата
    df = process_merged_cells(df)
    
    # Обрабатываем номера смен
    df = process_shift_numbers(df)

    # Преобразуем дату
    df["Дата"] = pd.to_datetime(df["Дата"], errors="coerce").dt.date
    df = df.dropna(subset=["Дата"])

    # Преобразуем время
    df["Время"] = df["Время"].apply(normalize_time_str)

    # Преобразуем числовые столбцы
    for col in df.columns:
        if col not in ["Дата", "Время", "№ смены"]:
            # Обрабатываем формулы (начинаются с =)
            if df[col].astype(str).str.startswith('=').any():
                # Для формул просто преобразуем в числа, Excel уже вычислил значения
                df[col] = pd.to_numeric(df[col], errors='coerce')
            else:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    # Комбинированная колонка
    df["Дата_Время"] = df["Дата"].astype(str) + " " + df["Время"].astype(str)

    numeric_cols = [c for c in df.select_dtypes(include=["int64", "float64"]).columns if c not in ["№ смены"]]

    # ======== ФИЛЬТРЫ В САЙДБАРЕ ========
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔧 Фильтры")
    
    # Создаем дерево дат
    date_tree = create_date_tree(df)
    
    # Фильтр по времени смены
    shift_options = sorted(df["Время"].dropna().unique().tolist())
    selected_shifts = st.sidebar.multiselect(
        "Выберите время смены:", 
        shift_options, 
        default=shift_options
    )
    
    # Фильтр по номеру смены
    shift_number_options = sorted(df["№ смены"].dropna().unique().tolist())
    selected_shift_numbers = st.sidebar.multiselect(
        "Выберите номер смены:",
        shift_number_options,
        default=shift_number_options
    )
    
    # Дерево выбора дат
    st.sidebar.markdown("### 📅 Выбор дат")
    
    months_dict = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    
    selected_dates = set()
    
    for year in sorted(date_tree.keys()):
        with st.sidebar.expander(str(year)):
            year_key = f"select_all_year_{year}"
            select_all_year = st.checkbox("Выбрать все в году", value=False, key=year_key)
            
            if select_all_year:
                for month in date_tree[year]:
                    for week in date_tree[year][month]:
                        for day in date_tree[year][month][week]:
                            selected_dates.add(datetime(year, month, day).date())
            else:
                for month in sorted(date_tree[year].keys()):
                    month_name = months_dict[month]
                    with st.expander(month_name):
                        month_key = f"select_all_month_{year}_{month}"
                        select_all_month = st.checkbox("Выбрать все в месяце", value=False, key=month_key)
                        
                        if select_all_month:
                            for week in date_tree[year][month]:
                                for day in date_tree[year][month][week]:
                                    selected_dates.add(datetime(year, month, day).date())
                        else:
                            for week in sorted(date_tree[year][month].keys()):
                                with st.expander(f"Неделя {week}"):
                                    week_key = f"select_all_week_{year}_{month}_{week}"
                                    select_all_week = st.checkbox("Выбрать все в неделе", value=False, key=week_key)
                                    
                                    if select_all_week:
                                        for day in date_tree[year][month][week]:
                                            selected_dates.add(datetime(year, month, day).date())
                                    else:
                                        for day in sorted(date_tree[year][month][week]):
                                            day_key = f"day_{year}_{month}_{week}_{day}"
                                            select_day = st.checkbox(str(day), value=False, key=day_key)
                                            if select_day:
                                                selected_dates.add(datetime(year, month, day).date())

    # Показываем предупреждение, если ничего не выбрано
    if not selected_dates:
        st.sidebar.warning("ℹ️ Не выбрано ни одной даты. Данные не будут отображаться.")

    # Применяем фильтры
    df_filtered = df[
        (df["Время"].isin(selected_shifts)) &
        (df["№ смены"].isin(selected_shift_numbers))
    ].copy()
    
    # Применяем фильтр по датам только если есть выбранные даты
    if selected_dates:
        df_filtered = df_filtered[df_filtered["Дата"].isin(selected_dates)]
    else:
        # Если даты не выбраны, создаем пустой DataFrame с теми же колонками
        df_filtered = pd.DataFrame(columns=df.columns)

    # Проверяем, есть ли данные для отображения
    if df_filtered.empty:
        st.info("📅 Выберите даты в сайдбаре для отображения данных")
        # Останавливаем выполнение кода дальше, чтобы не было ошибок
        st.stop()

    # ======== БЛОК ИНФОРМАЦИИ О ДАННЫХ ========
    st.title("📦 Дашборд по складу: динамика и показатели")
    
    
    # ======== KPI БЛОК ========
    st.subheader("🔹 Сводные KPI за выбранный период")

    def safe_sum(col):
        return df_filtered[col].sum() if col in df_filtered.columns else 0

    def safe_mean(col):
        return df_filtered[col].mean() if col in df_filtered.columns else 0

    total_turnover = safe_sum("Грузооборот всего")
    avg_turnover = safe_mean("Грузооборот всего")
    total_unloaded = safe_sum("Разгружено машин")
    total_loaded = safe_sum("Загружено машин")

    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(f"<div class='kpi-card'><div class='kpi-value'>{total_turnover:,.0f}</div><div class='kpi-label'>Грузооборот всего</div></div>", unsafe_allow_html=True)
    col2.markdown(f"<div class='kpi-card'><div class='kpi-value'>{avg_turnover:,.0f}</div><div class='kpi-label'>Средний грузооборот</div></div>", unsafe_allow_html=True)
    col3.markdown(f"<div class='kpi-card'><div class='kpi-value'>{total_unloaded:,.0f}</div><div class='kpi-label'>Разгружено машин</div></div>", unsafe_allow_html=True)
    col4.markdown(f"<div class='kpi-card'><div class='kpi-value'>{total_loaded:,.0f}</div><div class='kpi-label'>Загружено машин</div></div>", unsafe_allow_html=True)

    # ======== ГЛАВНАЯ ========
    if page == "Главная":
        st.markdown("### 📋 Таблица по выбранным данным")
        st.dataframe(df_filtered, use_container_width=True)

    # ======== ДИНАМИКА ========
    elif page == "Динамика":
        st.markdown("### 📈 Динамика показателей")
        selected_metric = st.multiselect("Выберите показатели:", numeric_cols, default=["Грузооборот всего"])
        
        if selected_metric:
            # Создаем копию данных для построения графика
            plot_df = df_filtered.copy()
            plot_df = plot_df.sort_values('Дата_Время')
            
            # Добавляем числовой индекс для построения тренда
            plot_df['x_index'] = range(len(plot_df))
            
            # Создаем длинный формат данных для Plotly
            long_df = pd.melt(plot_df, id_vars=["Дата_Время", "x_index"], value_vars=selected_metric,
                              var_name="Показатель", value_name="Значение")
            
            # Создаем график
            fig = px.bar(long_df, x="Дата_Время", y="Значение", color="Показатель",
                         title="Изменения показателей по датам и времени",
                         barmode='group')
            
            # Добавляем тренд если выбран только один показатель
            if len(selected_metric) == 1:
                show_trend = st.checkbox("Показать линейный тренд", value=True)
                
                if show_trend:
                    metric = selected_metric[0]
                    trend_line, slope, r_squared = calculate_trend(plot_df, 'x_index', metric)
                    
                    if trend_line is not None:
                        # Добавляем линию тренда
                        fig.add_trace(
                            go.Scatter(
                                x=plot_df["Дата_Время"],
                                y=trend_line,
                                mode='lines',
                                name=f'Тренд {metric}',
                                line=dict(color='red', width=3, dash='dash'),
                                showlegend=True
                            )
                        )
                        
                        # Показываем статистику тренда
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Наклон тренда", f"{slope:.2f}")
                        with col2:
                            st.metric("R² (качество аппроксимации)", f"{r_squared:.3f}")
            else:
                st.info("ℹ️ Для построения тренда выберите только один показатель")
            
            # Настройка внешнего вида
            fig.update_layout(
                xaxis_title="Дата и время",
                yaxis_title="Значение",
                legend_title="Показатели",
                xaxis_tickangle=-45
            )
            
            st.plotly_chart(fig, use_container_width=True)


    # ======== АНАЛИЗ ПО СМЕНАМ ========
    elif page == "Анализ по сменам":
        st.markdown("## 🔄 Анализ по сменам")
        
        # Явно указываем столбцы которые у нас есть
        vehicle_columns = [
            'Разгружено машин', 
            'Загружено машин', 
            'Разгружено тракторов', 
            'Загружено тракторов'
        ]
        
        pallet_columns = [
            'Принято паллет', 
            'Отгружено паллет', 
            'Паллет без системы'
        ]
        
        employee_columns = [
            'Старший смены',
            'Помощник старшего смены', 
            'Кладовщик',
            'Водитель погрузчика',
            'Рабочий склада',
            'Всего сотрудников'
        ]
        
        # Проверяем какие столбцы действительно есть в данных
        existing_vehicle_cols = [col for col in vehicle_columns if col in df_filtered.columns]
        existing_pallet_cols = [col for col in pallet_columns if col in df_filtered.columns]
        existing_employee_cols = [col for col in employee_columns if col in df_filtered.columns]        
        # Проверяем наличие столбца с общим количеством сотрудников
        if 'Всего сотрудников' not in df_filtered.columns:
            st.error("❌ Столбец 'Всего сотрудников' не найден в данных!")
            st.info("Доступные столбцы:")
            st.write(list(df_filtered.columns))
            st.stop()
        
        # Группируем по сменам
        shift_analysis = df_filtered.groupby('№ смены').agg({
            **{col: 'sum' for col in existing_vehicle_cols},
            **{col: 'sum' for col in existing_pallet_cols},
            **{col: 'sum' for col in existing_employee_cols},
            'Грузооборот всего': 'sum'
        }).reset_index()
        
        # Создаем две колонки для отображения
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🚛 Транспортные средства по сменам")
            
            if existing_vehicle_cols:
                # Создаем график для транспортных средств
                vehicle_melted = pd.melt(shift_analysis, 
                                        id_vars=['№ смены'], 
                                        value_vars=existing_vehicle_cols,
                                        var_name='Тип транспорта', 
                                        value_name='Количество')
                
                fig_vehicles = px.bar(vehicle_melted, 
                                     x='№ смены', 
                                     y='Количество', 
                                     color='Тип транспорта',
                                     title='Обработанные транспортные средства по сменам',
                                     barmode='group')
                
                fig_vehicles.update_layout(
                    xaxis_title="Номер смены",
                    yaxis_title="Количество",
                    legend_title="Тип транспорта"
                )
                
                st.plotly_chart(fig_vehicles, use_container_width=True)
                
                # Таблица с детализацией
                st.markdown("#### Детализация по транспортным средствам")
                vehicle_table = shift_analysis[['№ смены'] + existing_vehicle_cols]
                st.dataframe(vehicle_table, use_container_width=True)
            else:
                st.error("Не найдено столбцов с данными о транспортных средствах")
        
        with col2:
            st.markdown("### 📦 Паллеты по сменам")
            
            if existing_pallet_cols:
                # Создаем график для паллет
                pallet_melted = pd.melt(shift_analysis, 
                                       id_vars=['№ смены'], 
                                       value_vars=existing_pallet_cols,
                                       var_name='Тип операции', 
                                       value_name='Количество')
                
                fig_pallets = px.bar(pallet_melted, 
                                    x='№ смены', 
                                    y='Количество', 
                                    color='Тип операции',
                                    title='Принятые и отгруженные паллеты по сменам',
                                    barmode='group')
                
                fig_pallets.update_layout(
                    xaxis_title="Номер смены",
                    yaxis_title="Количество",
                    legend_title="Тип операции"
                )
                
                st.plotly_chart(fig_pallets, use_container_width=True)
                
                # Таблица с детализацией
                st.markdown("#### Детализация по паллетам")
                pallet_table = shift_analysis[['№ смены'] + existing_pallet_cols]
                st.dataframe(pallet_table, use_container_width=True)
            else:
                st.error("Не найдено столбцов с данными о паллетах")
        
        # Детализация по сотрудникам
        if len(existing_employee_cols) > 1:  # Если есть больше чем just 'Всего сотрудников'
            st.markdown("### 👥 Детализация по сотрудникам по сменам")
            
            # Создаем график для сотрудников
            employee_melted = pd.melt(shift_analysis, 
                                     id_vars=['№ смены'], 
                                     value_vars=[col for col in existing_employee_cols if col != 'Всего сотрудников'],
                                     var_name='Должность', 
                                     value_name='Количество')
            
            fig_employees = px.bar(employee_melted, 
                                  x='№ смены', 
                                  y='Количество', 
                                  color='Должность',
                                  title='Распределение сотрудников по должностям и сменам',
                                  barmode='stack')
            
            fig_employees.update_layout(
                xaxis_title="Номер смены",
                yaxis_title="Количество сотрудников",
                legend_title="Должность"
            )
            
            st.plotly_chart(fig_employees, use_container_width=True)
            
            # Таблица с детализацией по сотрудникам
            st.markdown("#### Детализация по сотрудникам")
            employee_table = shift_analysis[['№ смены'] + existing_employee_cols]
            st.dataframe(employee_table, use_container_width=True)
        
        # Сводная статистика по сменам
        st.markdown("### 📊 Сводная статистика по сменам")
        
        # Создаем карточки с KPI для каждой смены
        shifts = sorted(df_filtered['№ смены'].unique())
        
        for shift in shifts:
            shift_data = df_filtered[df_filtered['№ смены'] == shift]
            
            st.markdown(f"#### Смена {shift}")
            
            # Создаем колонки для метрик
            cols = st.columns(5)
            
            # Общее количество записей по смене
            with cols[0]:
                total_records = len(shift_data)
                st.metric("Всего записей", total_records)
            
            # Транспортные средства
            with cols[1]:
                if existing_vehicle_cols:
                    total_vehicles = shift_data[existing_vehicle_cols].sum().sum()
                    st.metric("Всего транспорта", f"{total_vehicles:,.0f}")
                else:
                    st.metric("Всего транспорта", "Нет данных")
            
            # Паллеты
            with cols[2]:
                if existing_pallet_cols:
                    total_pallets = shift_data[existing_pallet_cols].sum().sum()
                    st.metric("Всего паллет", f"{total_pallets:,.0f}")
                else:
                    st.metric("Всего паллет", "Нет данных")
            
            # Грузооборот
            with cols[3]:
                total_turnover = shift_data['Грузооборот всего'].sum()
                st.metric("Грузооборот", f"{total_turnover:,.0f}")
            
            # Состав смены - ТОЧНОЕ количество сотрудников из столбца 'Всего сотрудников'
            with cols[4]:
                # Суммируем сотрудников за все дни выбранного периода
                total_team = shift_data['Всего сотрудников'].sum()
                st.metric("Всего сотрудников", f"{total_team:,.0f}")
        
        # Дополнительная аналитика
        st.markdown("### 📈 Сравнительный анализ смен")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Эффективность по грузообороту на человека
            shift_analysis['Эффективность'] = shift_analysis['Грузооборот всего'] / shift_analysis['Всего сотрудников']
            
            fig_efficiency = px.bar(shift_analysis, 
                                   x='№ смены', 
                                   y='Эффективность',
                                   title='Эффективность по грузообороту на сотрудника по сменам',
                                   color='Эффективность')
            
            st.plotly_chart(fig_efficiency, use_container_width=True)
        
        with col2:
            # Общий грузооборот по сменам
            fig_turnover = px.pie(shift_analysis, 
                                 values='Грузооборот всего', 
                                 names='№ смены',
                                 title='Распределение грузооборота по сменам')
            
            st.plotly_chart(fig_turnover, use_container_width=True)
        
        # Детальная таблица всех показателей по сменам
        st.markdown("### 📋 Полная сводка по сменам")
        
        # Переименовываем столбцы для лучшего отображения
        display_columns = {
            '№ смены': 'Смена',
            'Грузооборот всего': 'Грузооборот',
            'Всего сотрудников': 'Всего сотрудников',
            'Эффективность': 'Эффективность (грузооборот/сотрудник)'
        }
        
        shift_display = shift_analysis.rename(columns=display_columns)
        st.dataframe(shift_display, use_container_width=True)

        # ======== СРЕДНИЕ ПОКАЗАТЕЛИ ПО СМЕНАМ ========
        st.markdown("### 📊 Средние показатели по сменам")
        
        if not df_filtered.empty:
            # Группируем по сменам и вычисляем средние значения
            shift_avg = df_filtered.groupby('№ смены').agg({
                'Грузооборот всего': 'mean',
                'Всего сотрудников': 'mean'
            }).round(2)
            
            # Добавляем средние по транспорту если есть данные
            if existing_vehicle_cols:
                vehicle_avg = df_filtered.groupby('№ смены')[existing_vehicle_cols].mean().round(2)
                shift_avg = pd.concat([shift_avg, vehicle_avg], axis=1)
            
            # Добавляем средние по паллетам если есть данные
            if existing_pallet_cols:
                pallet_avg = df_filtered.groupby('№ смены')[existing_pallet_cols].mean().round(2)
                shift_avg = pd.concat([shift_avg, pallet_avg], axis=1)
            
            # Переименовываем столбцы для лучшего отображения
            shift_avg_display = shift_avg.rename(columns={
                'Грузооборот всего': 'Средний грузооборот',
                'Всего сотрудников': 'Среднее количество сотрудников'
            })
            
            # Показываем таблицу средних значений
            st.markdown("#### Таблица средних показателей")
            st.dataframe(shift_avg_display, use_container_width=True)
            
            # Визуализация средних показателей
            col1, col2 = st.columns(2)
            
            with col1:
                # Средний грузооборот по сменам
                if 'Средний грузооборот' in shift_avg_display.columns:
                    fig_avg_turnover = px.bar(
                        shift_avg_display.reset_index(),
                        x='№ смены',
                        y='Средний грузооборот',
                        title='Средний грузооборот по сменам',
                        color='Средний грузооборот',
                        color_continuous_scale='Blues'
                    )
                    st.plotly_chart(fig_avg_turnover, use_container_width=True)
            
            with col2:
                # Среднее количество сотрудников по сменам
                if 'Среднее количество сотрудников' in shift_avg_display.columns:
                    fig_avg_employees = px.bar(
                        shift_avg_display.reset_index(),
                        x='№ смены',
                        y='Среднее количество сотрудников',
                        title='Среднее количество сотрудников по сменам',
                        color='Среднее количество сотрудников',
                        color_continuous_scale='Greens'
                    )
                    st.plotly_chart(fig_avg_employees, use_container_width=True)
            
            # Дополнительные средние показатели
            if existing_vehicle_cols or existing_pallet_cols:
                st.markdown("#### Дополнительные средние показатели")
                
                # Транспортные средства
                if existing_vehicle_cols:
                    st.markdown("##### 🚛 Средние показатели транспорта по сменам")
                    vehicle_avg_melted = pd.melt(
                        shift_avg_display[existing_vehicle_cols].reset_index(),
                        id_vars=['№ смены'],
                        value_vars=existing_vehicle_cols,
                        var_name='Тип транспорта',
                        value_name='Среднее количество'
                    )
                    
                    fig_avg_vehicles = px.bar(
                        vehicle_avg_melted,
                        x='№ смены',
                        y='Среднее количество',
                        color='Тип транспорта',
                        title='Среднее количество транспорта по сменам',
                        barmode='group'
                    )
                    st.plotly_chart(fig_avg_vehicles, use_container_width=True)
                
                # Паллеты
                if existing_pallet_cols:
                    st.markdown("##### 📦 Средние показатели паллет по сменам")
                    pallet_avg_melted = pd.melt(
                        shift_avg_display[existing_pallet_cols].reset_index(),
                        id_vars=['№ смены'],
                        value_vars=existing_pallet_cols,
                        var_name='Тип операции',
                        value_name='Среднее количество'
                    )
                    
                    fig_avg_pallets = px.bar(
                        pallet_avg_melted,
                        x='№ смены',
                        y='Среднее количество',
                        color='Тип операции',
                        title='Среднее количество паллет по сменам',
                        barmode='group'
                    )
                    st.plotly_chart(fig_avg_pallets, use_container_width=True)
    # ======== АНОМАЛИИ ========
    elif page == "Аномалии":
        st.markdown("## 🚨 Обнаружение аномалий")
        
        if df_filtered.empty:
            st.warning("Нет данных для анализа аномалий")
        else:
            # Выбор показателя для анализа аномалий
            anomaly_metric = st.selectbox(
                "Выберите показатель для анализа аномалий:",
                numeric_cols,
                index=numeric_cols.index("Грузооборот всего") if "Грузооборот всего" in numeric_cols else 0
            )
            
            # Настройка порога аномалий
            threshold = st.slider(
                "Порог аномалий (стандартные отклонения):",
                min_value=1.0,
                max_value=3.0,
                value=2.0,
                step=0.1,
                help="Значения, отклоняющиеся от среднего более чем на указанное количество стандартных отклонений, считаются аномалиями"
            )
            
            # Обнаруживаем аномалии
            anomalies = detect_anomalies(df_filtered, anomaly_metric, threshold)
            
            # Показываем статистику
            col1, col2, col3, col4 = st.columns(4)
            
            mean_val = df_filtered[anomaly_metric].mean()
            std_val = df_filtered[anomaly_metric].std()
            
            with col1:
                st.metric("Среднее значение", f"{mean_val:.2f}")
            with col2:
                st.metric("Стандартное отклонение", f"{std_val:.2f}")
            with col3:
                st.metric("Верхняя граница", f"{mean_val + threshold * std_val:.2f}")
            with col4:
                st.metric("Нижняя граница", f"{mean_val - threshold * std_val:.2f}")
            
            # Показываем аномалии
            if not anomalies.empty:
                st.markdown(f"### 📋 Обнаруженные аномалии ({len(anomalies)} записей)")
                
                # Визуализация аномалий
                fig_anomalies = go.Figure()
                
                # Добавляем нормальные точки
                normal_data = df_filtered[~df_filtered.index.isin(anomalies.index)]
                fig_anomalies.add_trace(
                    go.Scatter(
                        x=normal_data["Дата_Время"],
                        y=normal_data[anomaly_metric],
                        mode='markers',
                        name='Нормальные значения',
                        marker=dict(color='blue', size=8)
                    )
                )
                
                # Добавляем аномалии
                fig_anomalies.add_trace(
                    go.Scatter(
                        x=anomalies["Дата_Время"],
                        y=anomalies[anomaly_metric],
                        mode='markers',
                        name='Аномалии',
                        marker=dict(color='red', size=10, symbol='x')
                    )
                )
                
                # Добавляем линии границ
                fig_anomalies.add_hline(
                    y=mean_val + threshold * std_val,
                    line_dash="dash",
                    line_color="red",
                    annotation_text="Верхняя граница"
                )
                
                fig_anomalies.add_hline(
                    y=mean_val - threshold * std_val,
                    line_dash="dash",
                    line_color="red",
                    annotation_text="Нижняя граница"
                )
                
                fig_anomalies.update_layout(
                    title=f"Аномалии в показателе '{anomaly_metric}'",
                    xaxis_title="Дата и время",
                    yaxis_title=anomaly_metric,
                    showlegend=True
                )
                
                st.plotly_chart(fig_anomalies, use_container_width=True)
                
                # Таблица с деталями аномалий
                st.markdown("#### Детали аномалий")
                
                # Подготавливаем данные для отображения
                display_columns = ['Дата', 'Время', '№ смены', anomaly_metric, 'Тип аномалии', 'Отклонение', 'Отклонение в σ']
                available_columns = [col for col in display_columns if col in anomalies.columns]
                
                anomalies_display = anomalies[available_columns].copy()
                anomalies_display['Отклонение'] = anomalies_display['Отклонение'].round(2)
                anomalies_display['Отклонение в σ'] = anomalies_display['Отклонение в σ'].round(2)
                
                # Сортируем по отклонению (по абсолютному значению)
                anomalies_display = anomalies_display.reindex(
                    anomalies_display['Отклонение в σ'].abs().sort_values(ascending=False).index
                )
                
                st.dataframe(anomalies_display, use_container_width=True)
                
                # Опция экспорта аномалий
                csv = anomalies_display.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 Скачать аномалии как CSV",
                    data=csv,
                    file_name=f"аномалии_{anomaly_metric}.csv",
                    mime="text/csv"
                )
                
            else:
                st.success("🎉 Аномалий не обнаружено!")
    # ======== ИНСТРУКЦИЯ ========
    elif page == "Инструкция":
        st.markdown("# 📘 Инструкция по использованию дашборда")
        
        st.markdown("""
        <div class='instruction-card'>
        <h3>🎯 ОБЩЕЕ ОПИСАНИЕ</h3>
        <p>Этот дашборд предназначен для анализа данных склада, включая грузооборот, работу сотрудников, 
        транспортные операции и обработку паллет. Система позволяет визуализировать данные, обнаруживать 
        аномалии и анализировать эффективность работы по сменам.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Шаг 1 - Загрузка данных
        st.markdown("""
        <div class='instruction-card'>
        <h3><span class='step-number'>1</span> ЗАГРУЗКА ДАННЫХ</h3>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        **Требования к файлу:**
        - Формат: Excel (.xlsx)
        - Обязательный лист: "Грузооборот"
        - Обязательные столбцы: "Дата", "Время", "№ смены"
        
        **Поддерживаемые форматы времени смен:**
        - `6:00-18:00` (дневная смена)
        - `18:00-6:00` (ночная смена)
        - Также поддерживаются различные вариации написания
        """)
        
        st.markdown("""
        **Автоматическая обработка данных:**
        - Объединенные ячейки в столбце "Дата"
        - Преобразование буквенных обозначений смен в цифровые (А→1, Б→2 и т.д.)
        - Обработка формул Excel
        - Нормализация числовых данных
        """)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Шаг 2 - Фильтрация данных
        st.markdown("""
        <div class='instruction-card'>
        <h3><span class='step-number'>2</span> ФИЛЬТРАЦИЯ ДАННЫХ</h3>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        **Доступные фильтры в сайдбаре:**
        
        **1. Время смены:**
        - Выбор дневных/ночных смен
        - Множественный выбор
        
        **2. Номер смены:**
        - Фильтрация по конкретным сменам (1, 2, 3, 4)
        - Множественный выбор
        
        **3. Дерево дат:**
        - Иерархический выбор: Год → Месяц → Неделя → День
        - Возможность массового выбора ("Выбрать все")
        - Автоматическая группировка по календарю
        """)
        
        st.markdown("""
        <div class='warning-block'>
        ⚠️ <strong>Важно:</strong> Если не выбрано ни одной даты, данные не будут отображаться!
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Шаг 3 - Страницы анализа
        st.markdown("""
        <div class='instruction-card'>
        <h3><span class='step-number'>3</span> СТРАНИЦЫ АНАЛИЗА</h3>
        """, unsafe_allow_html=True)
        
        # Главная страница
        st.markdown("""
        <div class='feature-block'>
        <h4>🏠 ГЛАВНАЯ СТРАНИЦА</h4>
        - <strong>KPI-панель:</strong> Сводные показатели за выбранный период
        - <strong>Таблица данных:</strong> Полная таблица с отфильтрованными данными
        - <strong>Автоматическое обновление:</strong> Все показатели обновляются при изменении фильтров
        </div>
        """, unsafe_allow_html=True)
        
        # Динамика
        st.markdown("""
        <div class='feature-block'>
        <h4>📈 ДИНАМИКА</h4>
        - <strong>Выбор показателей:</strong> Множественный выбор метрик для сравнения
        - <strong>Столбчатые диаграммы:</strong> Визуализация изменений во времени
        - <strong>Линейный тренд:</strong> Построение тренда для одиночного показателя
        - <strong>Статистика тренда:</strong> Наклон и коэффициент детерминации R²
        </div>
        """, unsafe_allow_html=True)
        
        # Анализ по сменам
        st.markdown("""
        <div class='feature-block'>
        <h4>🔄 АНАЛИЗ ПО СМЕНАМ</h4>
        
        <strong>Средние показатели:</strong>
        - Средний грузооборот по сменам
        - Среднее количество сотрудников
        - Средние показатели транспорта и паллет
        
        <strong>Суммарные показатели:</strong>
        - Общий грузооборот по сменам
        - Суммарные данные по транспорту
        - Суммарные данные по паллетам
        - Визуализация в виде группированных столбчатых диаграмм
        
        <strong>Эффективность:</strong>
        - Расчет эффективности (грузооборот на сотрудника)
        - Сравнительный анализ смен
        </div>
        """, unsafe_allow_html=True)
        
        # Аномалии
        st.markdown("""
        <div class='feature-block'>
        <h4>🚨 АНОМАЛИИ</h4>
        
        <strong>Метод обнаружения:</strong>
        - Статистический метод стандартных отклонений
        - Настраиваемый порог (1-3 стандартных отклонения)
        - Автоматическое вычисление границ
        
        <strong>Визуализация:</strong>
        - Точечная диаграмма с выделением аномалий
        - Линии границ аномалий
        - Цветовое кодирование (нормальные/аномальные значения)
        
        <strong>Детальная информация:</strong>
        - Таблица с деталями аномалий
        - Тип аномалии (высокая/низкая)
        - Величина отклонения в стандартных отклонениях
        - Возможность экспорта в CSV
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Шаг 4 - Интерпретация результатов
        st.markdown("""
        <div class='instruction-card'>
        <h3><span class='step-number'>4</span> ИНТЕРПРЕТАЦИЯ РЕЗУЛЬТАТОВ</h3>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        **Ключевые метрики:**
        
        **Грузооборот:**
        - Основной показатель производительности склада
        - Анализ эффективности по сменам
        - Выявление сезонных тенденций
        
        **Транспортные операции:**
        - Баланс между разгрузкой и загрузкой
        - Эффективность использования транспорта
        - Планирование ресурсов
        
        **Персонал:**
        - Оптимальное распределение сотрудников
        - Анализ эффективности работы
        - Выявление потребности в дополнительных ресурсах
        
        **Аномалии:**
        - Выявление нестандартных ситуаций
        - Анализ причин пиков/спадов
        - Проактивное управление процессами
        """)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Советы и рекомендации
        st.markdown("""
        <div class='instruction-card'>
        <h3>💡 СОВЕТЫ И РЕКОМЕНДАЦИИ</h3>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        1. **Регулярное обновление данных** - загружайте актуальные данные для точного анализа
        2. **Используйте фильтры** - анализируйте конкретные периоды и смены для точных выводов
        3. **Сравнивайте показатели** - используйте страницу "Динамика" для выявления тенденций
        4. **Исследуйте аномалии** - анализируйте причины нестандартных значений
        5. **Экспортируйте данные** - используйте функцию скачивания для дальнейшего анализа
        6. **Настраивайте пороги** - адаптируйте чувствительность обнаружения аномалий под ваши данные
        """)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
else:
    st.info("📁 Загрузите Excel-файл с листом 'Грузооборот' для начала.")
