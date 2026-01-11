import streamlit as st
from pypdf import PdfReader

# --- ФУНКЦИЯ ОЧИСТКИ ТЕКСТА ---
def clean_text(raw_text):
    if not raw_text:
        return ""
        
    lines = raw_text.split('\n')
    res = ""
    buf = ""
    # Символы переноса
    hyphens = ['-', '\xad', '\u2010', '\u2011', '\u2012', '\u2013', '\u2014']

    for line in lines:
        s = line.strip()
        if not s or s.isdigit(): 
            continue

        is_new = s[0].isupper() if s else False
        is_end = buf.endswith(('.', '!', '?'))

        if (is_end and is_new) and buf:
            res += buf + "\n\n"
            buf = s
        else:
            if any(buf.endswith(h) for h in hyphens):
                buf = buf[:-1] + s
            else:
                buf += " " + s
                
    return res + buf

# --- ИНТЕРФЕЙС ---
st.title("PDF Text Extractor Pro")

# 1. Загрузка
uploaded_file = st.file_uploader("Загрузите PDF файл", type="pdf")

if uploaded_file is not None:
    pdf = PdfReader(uploaded_file)
    total_pages = len(pdf.pages)
    
    st.write(f"Всего страниц в документе: {total_pages}")
    
    # 2. Выбор режима
    mode = st.radio("Режим обработки:", ["По номерам страниц", "По фразам (от и до)"], horizontal=True)
    
    start_page = 1
    end_page = 1
    start_phrase = ""
    end_phrase = ""
    
    # Настройки интерфейса
    if mode == "По номерам страниц":
        col1, col2 = st.columns(2)
        with col1:
            start_page = st.number_input("От стр", min_value=1, max_value=total_pages, value=1)
        with col2:
            default_end = min(start_page + 5, total_pages)
            end_page = st.number_input("До стр", min_value=start_page, max_value=total_pages, value=default_end)
            
    else: # Режим "По фразам"
        st.info("Поиск будет производиться по всему документу.")
        col1, col2 = st.columns(2)
        with col1:
            start_phrase = st.text_input("Начальная фраза (откуда копировать)")
        with col2:
            end_phrase = st.text_input("Конечная фраза (докуда копировать)")

    # 3. Кнопка запуска
    if st.button("Извлечь текст"):
        
        final_text = ""
        error_msg = ""
        
        with st.spinner("Обработка... (для больших книг поиск фраз может занять время)"):
            
            # СЦЕНАРИЙ 1: ПО СТРАНИЦАМ
            if mode == "По номерам страниц":
                raw_chunk = ""
                for i in range(start_page - 1, end_page):
                    content = pdf.pages[i].extract_text()
                    if content:
                        raw_chunk += content + "\n"
                final_text = clean_text(raw_chunk)

            # СЦЕНАРИЙ 2: ПО ФРАЗАМ
            else:
                if not start_phrase or not end_phrase:
                    error_msg = "Введите обе фразы: начальную и конечную."
                else:
                    # Считываем ВЕСЬ текст, чтобы найти фразы (это может занять секунды для больших книг)
                    full_raw_text = ""
                    for page in pdf.pages:
                        full_raw_text += page.extract_text() + "\n"
                    
                    # Сначала чистим весь текст (чтобы убрать переносы и найти фразы точно)
                    full_cleaned = clean_text(full_raw_text)
                    
                    # Ищем индексы вхождения
                    # Приводим к нижнему регистру для поиска, чтобы не зависеть от заглавных букв
                    idx_start = full_cleaned.lower().find(start_phrase.lower())
                    
                    if idx_start == -1:
                        error_msg = "Начальная фраза не найдена в тексте."
                    else:
                        # Ищем конец ПОСЛЕ начала
                        idx_end = full_cleaned.lower().find(end_phrase.lower(), idx_start)
                        
                        if idx_end == -1:
                            error_msg = "Конечная фраза не найдена (после начальной)."
                        else:
                            # Вырезаем кусок. 
                            # + len(end_phrase) чтобы включить саму конечную фразу в результат
                            final_text = full_cleaned[idx_start : idx_end + len(end_phrase)]

        # --- ВЫВОД РЕЗУЛЬТАТА ---
        if error_msg:
            st.error(error_msg)
        elif final_text:
            st.subheader("Результат:")
            
            # --- СЧЕТЧИК А4 ---
            # Удаляем пробелы, переносы строк и табуляцию для подсчета символов
            chars_no_spaces = len(final_text.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", ""))
            pages_count = chars_no_spaces / 1725
            
            # Отображаем красивые метрики
            m1, m2 = st.columns(2)
            m1.metric("Символов (без пробелов)", chars_no_spaces)
            m2.metric("Страниц А4 (1725 зн)", f"{pages_count:.2f}")
            
            # Текстовое поле
            st.text_area("Извлеченный текст", final_text, height=500)
            
            st.download_button(
                label="Скачать результат (.txt)",
                data=final_text,
                file_name="extracted_text.txt",
                mime="text/plain"
            )
