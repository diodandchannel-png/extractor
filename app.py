import streamlit as st
from pypdf import PdfReader
import re
# Попытка импорта для предотвращения ошибки, если библиотека еще не встала
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

    # Подготовка списка стоп-фраз (приводим к нижнему регистру для поиска)
    stop_phrases_lower = [p.lower().strip() for p in stop_phrases] if stop_phrases else []

    for line in lines:
        s = line.strip()
        if not s or s.isdigit(): 
            continue

        # --- ФИЛЬТР 1: Пользовательские стоп-фразы ---
        # Если строка содержит запрещенную фразу целиком
        if any(phrase in s.lower() for phrase in stop_phrases_lower):
            continue

        # --- ФИЛЬТР 2: Авто-удаление служебных строк (Колонтитулы с цифрами) ---
        # Пример: "Отечественные архивы. 2000. № 4"
        is_upper = s[0].isupper()
        ends_punct = s.endswith(('.', '!', '?', ',', ';', ':'))
        has_digits = any(char.isdigit() for char in s)
        
        # Если начинается с Большой, есть цифры, но нет точки в конце — скорее всего мусор
        if is_upper and not ends_punct and has_digits:
            continue
            
        # --- ФИЛЬТР 3: Сноски внутри строки ---
        # Убираем цифры, прилипшие к словам (среде5 -> среде)
        s = re.sub(r'([а-яА-ЯёЁa-zA-Z])\d{1,3}\b', r'\1', s)
        s = re.sub(r'([”"»])\d{1,3}\b', r'\1', s)

        # --- ЛОГИКА СКЛЕЙКИ ---
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
st.set_page_config(page_title="PDF Cleaner Pro", layout="wide")
st.title("PDF Text Extractor Pro 4.0")

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.header("Настройки очистки")
    st.write("Вставьте сюда повторяющиеся заголовки или мусор, который нужно удалить (каждую фразу с новой строки):")
    stop_phrases_input = st.text_area("Черный список фраз", height=150, placeholder="Например:\nСтатьи и сообщения\nГлава\nОтечественные архивы")
    
    st.markdown("---")
    st.header("AI Настройки")
    openai_api_key = st.text_input("OpenAI API Key (необязательно)", type="password")

# --- ОСНОВНАЯ ЧАСТЬ ---
uploaded_file = st.file_uploader("Загрузите PDF файл", type="pdf")

if uploaded_file is not None:
    pdf = PdfReader(uploaded_file)
    total_pages = len(pdf.pages)
    
    st.success(f"Файл загружен. Страниц: {total_pages}")
    
    # Режим
    mode = st.radio("Режим:", ["По номерам страниц", "По фразам (от и до)"], horizontal=True)
    
    start_page = 1
    end_page = 1
    start_phrase = ""
    end_phrase = ""
    
    if mode == "По номерам страниц":
        c1, c2 = st.columns(2)
        with c1:
            start_page = st.number_input("От стр", 1, total_pages, 1)
        with c2:
            default_end = min(start_page + 5, total_pages)
            end_page = st.number_input("До стр", start_page, total_pages, default_end)
    else: 
        st.info("Поиск фраз по всему документу")
        c1, c2 = st.columns(2)
        with c1:
            start_phrase = st.text_input("Начало")
        with c2:
            end_phrase = st.text_input("Конец")

    if 'generated_text' not in st.session_state:
        st.session_state.generated_text = ""

    # Кнопка запуска
    if st.button("🚀 Извлечь текст"):
        # Собираем список стоп-фраз из текстового поля
        stop_list = stop_phrases_input.split('\n')
        
        final_text = ""
        error_msg = ""
        
        with st.spinner("Обработка..."):
            # 1. СБОР СЫРОГО ТЕКСТА
            raw_full = ""
            if mode == "По номерам страниц":
                for i in range(start_page - 1, end_page):
                    content = pdf.pages[i].extract_text()
                    if content: raw_full += content + "\n"
            else:
                for page in pdf.pages:
                    content = page.extract_text()
                    if content: raw_full += content + "\n"

            # 2. ОЧИСТКА (передаем черный список)
            cleaned_full = clean_text(raw_full, stop_phrases=stop_list)

            # 3. ОБРЕЗКА ПО ФРАЗАМ (если выбран этот режим)
            if mode == "По фразам (от и до)":
                if not start_phrase or not end_phrase:
                    error_msg = "Введите обе фразы поиска!"
                else:
                    idx_start = cleaned_full.lower().find(start_phrase.lower())
                    if idx_start == -1:
                        error_msg = "Начальная фраза не найдена."
                    else:
                        idx_end = cleaned_full.lower().find(end_phrase.lower(), idx_start)
                        if idx_end == -1:
                            error_msg = "Конечная фраза не найдена."
                        else:
                            final_text = cleaned_full[idx_start : idx_end + len(end_phrase)]
            else:
                final_text = cleaned_full

        if error_msg:
            st.error(error_msg)
        else:
            st.session_state.generated_text = final_text

    # ВЫВОД РЕЗУЛЬТАТА
    if st.session_state.generated_text:
        txt = st.session_state.generated_text
        chars = len(txt.replace(" ", "").replace("\n", "").replace("\r", ""))
        pages = chars / 1725
        
        st.markdown("---")
        m1, m2 = st.columns(2)
        m1.metric("Символов (без пробелов)", chars)
        m2.metric("Страниц А4", f"{pages:.2f}")

        # Кнопки AI
        c_tools1, c_tools2 = st.columns(2)
        with c_tools1:
            if AI_SPELLER_OK:
                if st.button("✨ Исправить опечатки (Yandex)"):
                    with st.spinner("Работаю..."):
                        speller = YandexSpeller()
                        st.session_state.generated_text = speller.spelled(txt)
                        st.success("Готово!")
                        st.rerun()
            else:
                st.warning("Библиотека pyaspeller не найдена. Обновите requirements.txt!")

        with c_tools2:
            if openai_api_key:
                if st.button("🧠 AI Рерайт (GPT)"):
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=openai_api_key)
                        with st.spinner("AI думает..."):
                            resp = client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[{"role": "user", "content": f"Исправь ошибки и стиль: {txt}"}]
                            )
                            st.session_state.generated_text = resp.choices[0].message.content
                            st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка: {e}")

        st.text_area("Результат", st.session_state.generated_text, height=600)
        st.download_button("💾 Скачать .txt", st.session_state.generated_text, "text.txt")
