import streamlit as st
from pypdf import PdfReader

# --- ФУНКЦИЯ ОЧИСТКИ ТЕКСТА ---
def clean_text(raw_text):
    if not raw_text:
        return ""
        
    lines = raw_text.split('\n')
    res = ""
    buf = ""
    # Символы, которые считаем переносами
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
st.title("PDF Text Extractor")

# 1. Загрузка
uploaded_file = st.file_uploader("Загрузите PDF файл", type="pdf")

if uploaded_file is not None:
    # Читаем PDF (но пока не обрабатываем текст)
    pdf = PdfReader(uploaded_file)
    total_pages = len(pdf.pages)
    
    st.write(f"Всего страниц в документе: {total_pages}")
    
    # 2. Выбор режима (как на скриншоте)
    mode = st.radio("Режим:", ["Страницы", "Поиск по фразе"], horizontal=True)
    
    start_page = 1
    end_page = 1
    search_phrase = ""
    
    # Настройки в зависимости от режима
    if mode == "Страницы":
        col1, col2 = st.columns(2)
        with col1:
            start_page = st.number_input("От стр", min_value=1, max_value=total_pages, value=1)
        with col2:
            default_end = min(start_page + 5, total_pages)
            end_page = st.number_input("До стр", min_value=start_page, max_value=total_pages, value=default_end)
            
    else: # Режим фразы
        search_phrase = st.text_input("Введите фразу для поиска страниц")

    # 3. Кнопка запуска (ТЕПЕРЬ ТЕКСТ ПОЯВИТСЯ ТОЛЬКО ПОСЛЕ НАЖАТИЯ)
    if st.button("Получить текст"):
        
        raw_text = ""
        st.info("Обработка началась...")
        
        # ЛОГИКА ОБРАБОТКИ
        if mode == "Страницы":
            # Просто берем диапазон
            for i in range(start_page - 1, end_page):
                page_content = pdf.pages[i].extract_text()
                if page_content:
                    raw_text += page_content + "\n"
                    
        else: # Режим фразы
            if search_phrase:
                # Ищем фразу на всех страницах
                found_count = 0
                for i, page in enumerate(pdf.pages):
                    content = page.extract_text()
                    if content and search_phrase.lower() in content.lower():
                        raw_text += f"\n--- Страница {i+1} ---\n"
                        raw_text += content + "\n"
                        found_count += 1
                
                if found_count == 0:
                    st.warning("Фраза не найдена.")
            else:
                st.warning("Введите фразу.")

        # Очистка и вывод (если текст найден)
        if raw_text:
            cleaned_text = clean_text(raw_text)
            
            st.subheader("Результат:")
            st.text_area("Текст", cleaned_text, height=600)
            
            st.download_button(
                label="Скачать результат (.txt)",
                data=cleaned_text,
                file_name="result.txt",
                mime="text/plain"
            )
