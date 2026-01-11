import streamlit as st
from pypdf import PdfReader
import re

# Попытка импорта библиотек
try:
    from pyaspeller import YandexSpeller
    AI_SPELLER_OK = True
except ImportError:
    AI_SPELLER_OK = False

# --- 1. ФУНКЦИЯ ОЧИСТКИ ---
def clean_text(raw_text, stop_phrases=None):
    if not raw_text:
        return ""
        
    lines = raw_text.split('\n')
    res = ""
    buf = ""
    hyphens = ['-', '\xad', '\u2010', '\u2011', '\u2012', '\u2013', '\u2014']

    # ВАЖНОЕ ИСПРАВЛЕНИЕ: Фильтруем пустые строки в стоп-фразах
    stop_phrases_lower = []
    if stop_phrases:
        stop_phrases_lower = [p.lower().strip() for p in stop_phrases if p.strip()]

    for line in lines:
        s = line.strip()
        if not s or s.isdigit(): 
            continue

        # --- ФИЛЬТР 1: Черный список ---
        # Теперь срабатывает только если есть реальные фразы
        if stop_phrases_lower:
            if any(phrase in s.lower() for phrase in stop_phrases_lower):
                continue

        # --- ФИЛЬТР 2: Авто-удаление колонтитулов ---
        # (Заглавная + цифры + нет точки в конце)
        if s[0].isupper() and not s.endswith(('.', '!', '?', ',', ';', ':')) and any(c.isdigit() for c in s):
            continue
            
        # --- ФИЛЬТР 3: Сноски ---
        s = re.sub(r'([а-яА-ЯёЁa-zA-Z])\d{1,3}\b', r'\1', s)
        s = re.sub(r'([”"»])\d{1,3}\b', r'\1', s)

        # Склейка абзацев
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

# --- 2. ИНТЕРФЕЙС ---
st.set_page_config(page_title="PDF Pro 4.2", layout="wide")
st.title("PDF Text Extractor Pro 4.2")

with st.sidebar:
    st.header("Настройки")
    st.write("Черный список фраз (удалит строку, если найдет совпадение):")
    stop_phrases_input = st.text_area("Список", height=100, placeholder="Статьи и сообщения\nГлава")
    st.markdown("---")
    openai_api_key = st.text_input("OpenAI API Key (необязательно)", type="password")

uploaded_file = st.file_uploader("Загрузите PDF", type="pdf")

if uploaded_file is not None:
    pdf = PdfReader(uploaded_file)
    total_pages = len(pdf.pages)
    
    st.info(f"Файл загружен. Всего страниц: {total_pages}")
    
    mode = st.radio("Режим:", ["По номерам страниц", "По фразам (от и до)"], horizontal=True)
    
    start_page = 1
    end_page = 1
    start_phrase = ""
    end_phrase = ""
    
    if mode == "По номерам страниц":
        c1, c2 = st.columns(2)
        start_page = c1.number_input("От стр", 1, total_pages, 1)
        end_page = c2.number_input("До стр", start_page, total_pages, min(start_page + 5, total_pages))
    else: 
        c1, c2 = st.columns(2)
        start_phrase = c1.text_input("Начало")
        end_phrase = c2.text_input("Конец")

    if 'generated_text' not in st.session_state:
        st.session_state.generated_text = ""

    # КНОПКА ЗАПУСКА
    if st.button("🚀 Извлечь текст"):
        # Превращаем текст из поля в список, убирая пустые строки
        stop_list = [line.strip() for line in stop_phrases_input.split('\n') if line.strip()]
        
        final_text = ""
        error_msg = ""
        
        with st.spinner("Обработка..."):
            # Чтение
            raw_full = ""
            if mode == "По номерам страниц":
                for i in range(start_page - 1, end_page):
                    content = pdf.pages[i].extract_text()
                    if content: raw_full += content + "\n"
            else:
                for page in pdf.pages:
                    content = page.extract_text()
                    if content: raw_full += content + "\n"

            # Проверка, не пустой ли файл
            if not raw_full.strip():
                error_msg = "Текст не найден! Возможно, это скан (картинка) или пустые страницы."
            else:
                # Очистка
                cleaned = clean_text(raw_full, stop_phrases=stop_list)
                
                # Обрезка по фразам
                if mode == "По фразам (от и до)":
                    if not start_phrase or not end_phrase:
                        error_msg = "Введите фразы для поиска!"
                    else:
                        idx1 = cleaned.lower().find(start_phrase.lower())
                        if idx1 == -1:
                            error_msg = "Начальная фраза не найдена."
                        else:
                            idx2 = cleaned.lower().find(end_phrase.lower(), idx1)
                            if idx2 == -1:
                                error_msg = "Конечная фраза не найдена."
                            else:
                                final_text = cleaned[idx1 : idx2 + len(end_phrase)]
                else:
                    final_text = cleaned
                
                # Если после очистки ничего не осталось
                if not error_msg and not final_text.strip():
                    error_msg = "Результат пуст. Возможно, фильтры удалили весь текст."

        if error_msg:
            st.error(error_msg)
            st.session_state.generated_text = "" # Сброс
        else:
            st.session_state.generated_text = final_text

    # ВЫВОД
    if st.session_state.generated_text:
        txt = st.session_state.generated_text
        chars = len(txt.replace(" ", "").replace("\n", "").replace("\r", ""))
        pages_count = chars / 1725
        
        st.markdown("---")
        m1, m2 = st.columns(2)
        m1.metric("Символов", chars)
        m2.metric("Страниц А4", f"{pages_count:.2f}")

        c1, c2 = st.columns(2)
        with c1:
            if AI_SPELLER_OK:
                if st.button("✨ Исправить опечатки (Yandex)"):
                    with st.spinner("Исправляю..."):
                        st.session_state.generated_text = YandexSpeller().spelled(txt)
                        st.rerun()
            else:
                st.warning("Библиотека pyaspeller не установлена")

        with c2:
            if openai_api_key:
                if st.button("🧠 AI Рерайт (GPT)"):
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=openai_api_key)
                        with st.spinner("AI работает..."):
                            resp = client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[{"role": "user", "content": f"Исправь ошибки: {txt}"}]
                            )
                            st.session_state.generated_text = resp.choices[0].message.content
                            st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка: {e}")

        st.text_area("Результат", st.session_state.generated_text, height=600)
        st.download_button("💾 Скачать .txt", st.session_state.generated_text, "text.txt")
