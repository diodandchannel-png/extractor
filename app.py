import streamlit as st
from pypdf import PdfReader
import re
from pyaspeller import YandexSpeller

# --- 1. ФУНКЦИЯ ОЧИСТКИ (С УДАЛЕНИЕМ СНОСОК И КОЛОНТИТУЛОВ) ---
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

        # --- НОВЫЙ ФИЛЬТР: Удаляем колонтитулы и служебные строки ---
        # Логика: если строка не заканчивается на знак препинания (. ! ? , ;)
        # И ПРИ ЭТОМ начинается с большой буквы, И содержит цифры (например, год или номер)
        # Мы считаем ее колонтитулом и пропускаем.
        is_uppercase_start = s[0].isupper()
        ends_with_punctuation = s.endswith(('.', '!', '?', ',', ';'))
        has_digits = any(char.isdigit() for char in s)
        
        if is_uppercase_start and not ends_with_punctuation and has_digits:
            # Это похоже на колонтитул, пропускаем
            continue
        # ---------------------------------------------------------

        # --- Удаление сносок (цифр в конце слов) ---
        # 1. Убираем цифры, прилипшие к буквам (среде5 -> среде)
        s = re.sub(r'([а-яА-ЯёЁa-zA-Z])\d{1,3}\b', r'\1', s)
        # 2. Убираем цифры, прилипшие к кавычкам (власти"5 -> власти")
        s = re.sub(r'([”"»])\d{1,3}\b', r'\1', s)

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
st.set_page_config(page_title="PDF Pro Extractor", layout="wide")
st.title("PDF Text Extractor Pro 3.1 (Final)")

# Боковая панель для настройки AI (если есть ключ)
with st.sidebar:
    st.header("Настройки AI (Опционально)")
    st.info("Код работает бесплатно. Но если у вас есть ключ OpenAI, вставьте его ниже для проверки смысла.")
    openai_api_key = st.text_input("OpenAI API Key", type="password")

uploaded_file = st.file_uploader("Загрузите PDF файл", type="pdf")

if uploaded_file is not None:
    pdf = PdfReader(uploaded_file)
    total_pages = len(pdf.pages)
    
    st.write(f"📄 Страниц в документе: **{total_pages}**")
    
    # Режим
    mode = st.radio("Режим обработки:", ["По номерам страниц", "По фразам (от и до)"], horizontal=True)
    
    start_page = 1
    end_page = 1
    start_phrase = ""
    end_phrase = ""
    
    if mode == "По номерам страниц":
        c1, c2 = st.columns(2)
        with c1:
            start_page = st.number_input("От стр", min_value=1, max_value=total_pages, value=1)
        with c2:
            default_end = min(start_page + 5, total_pages)
            end_page = st.number_input("До стр", min_value=start_page, max_value=total_pages, value=default_end)
            
    else: 
        st.info("🔍 Поиск фразы по всему документу (может занять время для больших книг)")
        c1, c2 = st.columns(2)
        with c1:
            start_phrase = st.text_input("Начало (фраза)")
        with c2:
            end_phrase = st.text_input("Конец (фраза)")

    if 'generated_text' not in st.session_state:
        st.session_state.generated_text = ""

    # --- КНОПКА ЗАПУСКА ---
    if st.button("🚀 Извлечь и Очистить"):
        final_text = ""
        error_msg = ""
        
        with st.spinner("Чтение и глубокая очистка..."):
            # СЦЕНАРИЙ 1
            if mode == "По номерам страниц":
                raw_chunk = ""
                for i in range(start_page - 1, end_page):
                    content = pdf.pages[i].extract_text()
                    if content:
                        raw_chunk += content + "\n"
                final_text = clean_text(raw_chunk)

            # СЦЕНАРИЙ 2
            else:
                if not start_phrase or not end_phrase:
                    error_msg = "Введите обе фразы!"
                else:
                    full_raw_text = ""
                    for page in pdf.pages:
                        full_raw_text += page.extract_text() + "\n"
                    
                    # Чистим весь текст ДО поиска, чтобы найти фразы даже если они были разорваны
                    full_cleaned = clean_text(full_raw_text)
                    
                    idx_start = full_cleaned.lower().find(start_phrase.lower())
                    if idx_start == -1:
                        error_msg = "❌ Начальная фраза не найдена."
                    else:
                        idx_end = full_cleaned.lower().find(end_phrase.lower(), idx_start)
                        if idx_end == -1:
                            error_msg = "❌ Конечная фраза не найдена (после начальной)."
                        else:
                            final_text = full_cleaned[idx_start : idx_end + len(end_phrase)]

        if error_msg:
            st.error(error_msg)
        else:
            st.session_state.generated_text = final_text

    # --- ВЫВОД ---
    if st.session_state.generated_text:
        text_to_show = st.session_state.generated_text
        
        # Статистика
        chars_no_spaces = len(text_to_show.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", ""))
        pages_count = chars_no_spaces / 1725
        
        st.markdown("---")
        st.subheader("Результат")
        
        m1, m2 = st.columns(2)
        m1.metric("Символов (без пробелов)", chars_no_spaces)
        m2.metric("Страниц А4", f"{pages_count:.2f}")

        # ПАНЕЛЬ ИНСТРУМЕНТОВ AI
        col_tools1, col_tools2 = st.columns(2)
        
        with col_tools1:
            if st.button("✨ Исправить опечатки (Бесплатно/Yandex)"):
                with st.spinner("Проверка орфографии..."):
                    speller = YandexSpeller()
                    fixed = speller.spelled(text_to_show)
                    st.session_state.generated_text = fixed
                    st.success("Орфография исправлена!")
                    st.rerun()

        with col_tools2:
            if openai_api_key:
                if st.button("🧠 Проверить адекватность (GPT)"):
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=openai_api_key)
                        with st.spinner("Нейросеть читает и правит текст..."):
                            response = client.chat.completions.create(
                                model="gpt-4o-mini", 
                                messages=[
                                    {"role": "system", "content": "Ты профессиональный редактор. Твоя задача: исправить пунктуацию, стиль и смысловые ошибки в тексте, полученном из PDF. Убери мусор, склей разрывы, сделай текст читаемым, но сохрани смысл."},
                                    {"role": "user", "content": text_to_show}
                                ]
                            )
                            st.session_state.generated_text = response.choices[0].message.content
                            st.success("Текст обработан нейросетью!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка API: {e}")
            else:
                st.button("🧠 Проверить адекватность (GPT)", disabled=True, help="Введите API ключ слева в меню")

        # Текстовое поле
        st.text_area("Готовый текст", st.session_state.generated_text, height=600)
        
        st.download_button(
            label="💾 Скачать результат (.txt)",
            data=st.session_state.generated_text,
            file_name="extracted_text.txt",
            mime="text/plain"
        )
