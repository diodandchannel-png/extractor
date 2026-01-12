import streamlit as st
import fitz  # Это библиотека PyMuPDF
import re

# --- ПОДКЛЮЧЕНИЕ ПРОВЕРКИ ОРФОГРАФИИ ---
try:
    from pyaspeller import YandexSpeller
    AI_SPELLER_OK = True
except ImportError:
    AI_SPELLER_OK = False

# --- 1. ФУНКЦИЯ ОЧИСТКИ ТЕКСТА ---
def clean_text(raw_text, stop_phrases=None, footer_marker=None):
    if not raw_text:
        return ""
    
    # Разбиваем на страницы
    pages = raw_text.split('---PAGE_BREAK---')
    processed_pages = []

    # Подготовка стоп-фраз
    stop_phrases_lower = []
    if stop_phrases:
        stop_phrases_lower = [p.lower().strip() for p in stop_phrases if p.strip()]

    for page in pages:
        if not page.strip(): continue
        
        # --- 1. Отрезаем подвал страницы (по маркеру) ---
        if footer_marker and footer_marker.lower() in page.lower():
            start_of_footer = page.lower().find(footer_marker.lower())
            page = page[:start_of_footer]

        lines = page.split('\n')
        res = ""
        buf = ""
        hyphens = ['-', '\xad', '\u2010', '\u2011', '\u2012', '\u2013', '\u2014']

        for line in lines:
            s = line.strip()
            if not s or s.isdigit(): continue

            # --- 2. Черный список фраз ---
            if stop_phrases_lower:
                if any(phrase in s.lower() for phrase in stop_phrases_lower):
                    continue

            # --- 3. Авто-удаление колонтитулов ---
            if s[0].isupper() and not s.endswith(('.', '!', '?', ',', ';', ':')) and any(c.isdigit() for c in s):
                continue
            
            # --- 4. Удаление сносок-цифр ---
            s = re.sub(r'([а-яА-ЯёЁa-zA-Z])\d{1,3}\b', r'\1', s)
            s = re.sub(r'([”"»])\d{1,3}\b', r'\1', s)

            # --- 5. Склейка абзацев ---
            is_new = s[0].isupper() if s else False
            is_end = buf.endswith(('.', '!', '?'))

            if (is_end and is_new) and buf:
                res += buf + "\n\n"
                buf = s
            else:
                # Если строка заканчивается на дефис — склеиваем
                if any(buf.endswith(h) for h in hyphens):
                    buf = buf[:-1] + s
                else:
                    # Иначе ставим пробел
                    buf += " " + s
        
        processed_pages.append(res + buf)
                
    return "\n\n".join(processed_pages)

# --- 2. ИНТЕРФЕЙС ---
st.set_page_config(page_title="Архивный Помощник 5.0", page_icon="📚", layout="wide")
st.title("PDF Text Extractor v5.0 (PyMuPDF Engine)")

with st.sidebar:
    st.header("Настройки")
    
    st.subheader("Фильтры")
    stop_input = st.text_area("Черный список (фразы для удаления):", height=100)
    footer_mark = st.text_input("Маркер конца страницы:", placeholder="Например: Примечания")
    
    st.markdown("---")
    openai_key = st.text_input("OpenAI API Key (опция)", type="password")

uploaded_file = st.file_uploader("Загрузите PDF", type="pdf")

if uploaded_file is not None:
    # Читаем файл новым движком (PyMuPDF)
    file_bytes = uploaded_file.read()
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    total_pages = len(doc)
    
    st.info(f"Файл загружен. Страниц: {total_pages}")
    
    mode = st.radio("Режим работы:", ["По номерам страниц", "По фразам (от и до)"], horizontal=True)
    
    if mode == "По номерам страниц":
        c1, c2 = st.columns(2)
        start_p = c1.number_input("От стр", 1, total_pages, 1)
        end_p = c2.number_input("До стр", start_p, total_pages, min(start_p + 5, total_pages))
    else:
        c1, c2 = st.columns(2)
        start_ph = c1.text_input("Начало (фраза)")
        end_ph = c2.text_input("Конец (фраза)")

    if 'text_result' not in st.session_state:
        st.session_state.text_result = ""

    if st.button("🚀 Обработать"):
        stop_list = [l.strip() for l in stop_input.split('\n') if l.strip()]
        
        with st.spinner("Умное извлечение текста..."):
            raw_data = ""
            
            # --- ЧТЕНИЕ НОВЫМ МЕТОДОМ ---
            # Выбираем диапазон чтения
            pages_to_read = range(total_pages) # По умолчанию всё (для поиска фраз)
            if mode == "По номерам страниц":
                pages_to_read = range(start_p - 1, end_p)
            
            for i in pages_to_read:
                try:
                    page = doc.load_page(i)
                    # get_text("text") умнее, чем extract_text() — он видит отступы
                    txt = page.get_text("text") 
                    if txt:
                        raw_data += txt + "---PAGE_BREAK---"
                except Exception as e:
                    st.warning(f"Ошибка на стр {i+1}: {e}")

            if not raw_data.strip():
                st.error("Текст не найден. Возможно, это скан без слоя распознавания.")
            else:
                # ОЧИСТКА
                cleaned = clean_text(raw_data, stop_phrases=stop_list, footer_marker=footer_mark)
                
                # ОБРЕЗКА ПО ФРАЗАМ
                if mode == "По фразам (от и до)":
                    if not start_ph or not end_ph:
                        st.error("Введите фразы для поиска!")
                    else:
                        idx1 = cleaned.lower().find(start_ph.lower())
                        if idx1 == -1:
                            st.error("Начальная фраза не найдена.")
                        else:
                            idx2 = cleaned.lower().find(end_ph.lower(), idx1)
                            if idx2 == -1:
                                st.error("Конечная фраза не найдена.")
                            else:
                                st.session_state.text_result = cleaned[idx1 : idx2 + len(end_ph)]
                else:
                    st.session_state.text_result = cleaned

    # ВЫВОД РЕЗУЛЬТАТА
    if st.session_state.text_result:
        txt = st.session_state.text_result
        chars = len(txt.replace(" ", "").replace("\n", "").replace("\r", ""))
        
        st.markdown("---")
        st.markdown(f"**Символов:** {chars} | **Страниц А4:** {chars/1725:.2f}")
        
        if AI_SPELLER_OK and st.button("✨ Исправить опечатки (Yandex)"):
            st.session_state.text_result = YandexSpeller().spelled(txt)
            st.rerun()
            
        st.text_area("Результат", st.session_state.text_result, height=600)
        st.download_button("💾 Скачать (.txt)", st.session_state.text_result, "extracted.txt")
