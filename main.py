import pandas as pd
import streamlit as st
import plotly.express as px
import re
from datetime import datetime

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
    </style>
""", unsafe_allow_html=True)

# ==================== САЙДБАР ======================
st.sidebar.title("📊 Навигация")
page = st.sidebar.radio(
    "Раздел:",
    ["Главная", "Динамика", "Процентные изменения", "Анализ по сменам"]
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
    
    # Информация о данных сразу под заголовком
    st.markdown("### 📊 Информация о загруженных данных")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class='info-card'>
            <h4>📁 Размер данных</h4>
            <p><strong>Строк:</strong> {df.shape[0]}</p>
            <p><strong>Столбцов:</strong> {df.shape[1]}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class='info-card'>
            <h4>📅 Диапазон дат</h4>
            <p><strong>Начало:</strong> {df['Дата'].min()}</p>
            <p><strong>Конец:</strong> {df['Дата'].max()}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        numeric_count = len(numeric_cols)
        categorical_count = df.shape[1] - numeric_count
        
        # Информация о номерах смен
        shift_counts = df["№ смены"].value_counts()
        st.markdown(f"""
        <div class='info-card'>
            <h4>📈 Типы данных</h4>
            <p><strong>Числовые:</strong> {numeric_count}</p>
            <p><strong>Категориальные:</strong> {categorical_count}</p>
            <p><strong>Уникальных смен:</strong> {len(shift_counts)}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Отображение списка столбцов
    st.markdown("#### 📋 Список столбцов")
    columns_info = []
    for i, col in enumerate(df.columns, 1):
        dtype = str(df[col].dtype)
        non_null = df[col].count()
        total = len(df)
        columns_info.append(f"{i}. **{col}** (*{dtype}*) - {non_null}/{total} заполнено")
    
    st.write("\n".join(columns_info))
    
    # Показываем уникальные значения времени и смен для проверки
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🕐 Уникальные значения времени")
        st.write(df["Время"].value_counts())
    
    with col2:
        st.markdown("#### 🔢 Уникальные значения смен")
        st.write(df["№ смены"].value_counts().sort_index())
    
    # Первые 5 строк
    st.markdown("#### 👀 Первые 5 строк данных")
    st.dataframe(df.head(), use_container_width=True)
    
    st.markdown("---")

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
            long_df = pd.melt(df_filtered, id_vars=["Дата_Время"], value_vars=selected_metric,
                              var_name="Показатель", value_name="Значение")
            
            # Столбчатая диаграмма
            fig = px.bar(long_df, x="Дата_Время", y="Значение", color="Показатель",
                         title="Изменения показателей по датам и времени",
                         barmode='group')  # 'group' для группировки столбцов
            
            # Настройка внешнего вида
            fig.update_layout(
                xaxis_title="Дата и время",
                yaxis_title="Значение",
                legend_title="Показатели",
                xaxis_tickangle=-45
            )
            
            st.plotly_chart(fig, use_container_width=True)

    # ======== ПРОЦЕНТНЫЕ ИЗМЕНЕНИЯ ========
    elif page == "Процентные изменения":
        st.markdown("### 📊 Процентные изменения показателей")
        df_change = df_filtered.copy()
        for col in numeric_cols:
            if col in df_change.columns:
                df_change[f"Δ {col} (%)"] = df_change[col].pct_change() * 100
        st.dataframe(df_change, use_container_width=True)

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
        
        st.write(f"**Найдены столбцы транспорта:** {existing_vehicle_cols}")
        st.write(f"**Найдены столбцы паллет:** {existing_pallet_cols}")
        st.write(f"**Найдены столбцы сотрудников:** {existing_employee_cols}")
        
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

else:
    st.info("📁 Загрузите Excel-файл с листом 'Грузооборот' для начала.")