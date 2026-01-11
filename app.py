import streamlit as st
from pypdf import PdfReader
import io

# Попытка импорта библиотек для OCR (распознавания текста с картинок)
# Если их нет, программа не сломается, просто отключит эту функцию.
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    OCR_OK = True
except ImportError:
    OCR_OK = False

# --- 1. ФУНКЦИЯ ОЧИСТКИ ТЕКСТА (ИСПРАВЛЕННАЯ) ---
def clean_text(raw_text):
    if not raw_text:
        return ""
        
    lines = raw_text.split('\n')
    res = ""
    buf = ""
    
    # Список символов переноса: обычный минус, мягкий перенос (\xad) и разные тире
    hyphens = ['-', '\xad', '\u2010', '\u2011', '\u2012', '\u2013', '\u2014']

    for line in lines:
        s = line.strip()
        # Пропускаем пустые строки и номера страниц (если строка - просто число)
        if not s or s.isdigit(): 
            continue

        # Проверка: начинается ли новая строка с большой буквы
        is_new = s[0].isupper() if s else False
        # Проверка: заканчивается ли буфер знаками препинания
        is_end = buf.endswith(('.', '!', '?'))

        # Логика разделения абзацев
        if (is_end and is_new) and buf:
            res += buf + "\n\n"
            buf = s
        else:
            # Если предыдущая строка заканчивается на перенос - склеиваем без пробела
            if any(buf.endswith(h) for h in hyphens):
                buf = buf[:-1] + s
            else:
                # Иначе склеиваем через пробел
                buf += " " + s
                
    return res + buf

# --- 2. ФУНКЦИЯ ЧТЕНИЯ PDF ---
def get_pdf_content(file_bytes, use_ocr=False):
    text = ""
    
    # Если выбран OCR и библиотеки установлены
    if use_ocr and OCR_OK:
        try:
            # Конвертируем PDF в картинки
            images = convert_from_bytes(file_bytes)
            # Распознаем текст с каждой картинки
            for img in images:
                text += pytesseract.image_to_string(img, lang='rus+eng') + "\n"
        except Exception as e:
            st.error(f"Ошибка OCR: {e}. Пробую обычный метод...")
            # Если OCR упал, пробуем обычный метод ниже
            use_ocr = False

    # Обычный метод (извлечение текстового слоя)
    if not use_ocr:
        pdf = PdfReader(io.BytesIO(file_bytes))
        for page in pdf.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
                
    return text

# --- 3. ИНТЕРФЕЙС (STREAMLIT) ---
st.title("PDF Text Extractor & Cleaner")

uploaded_file = st.file_uploader("Загрузите PDF файл", type="pdf")

if uploaded_file is not None:
    # Читаем файл в память
    file_bytes = uploaded_file.read()
    
    # Настройки в боковой панели
    st.sidebar.header("Настройки")
    
    # Чекбокс для OCR (доступен только если библиотеки установлены)
    use_ocr = st.sidebar.checkbox("Использовать OCR (для сканов)", value=False, disabled=not OCR_OK)
    if not OCR_OK:
        st.sidebar.warning("OCR недоступен (нет библиотек tesseract/poppler)")

    if st.button("Обработать файл"):
        with st.spinner("Обработка..."):
            # 1. Извлекаем сырой текст
            raw_text = get_pdf_content(file_bytes, use_ocr=use_ocr)
            
            # 2. Чистим текст
            cleaned_text = clean_text(raw_text)
            
            # 3. Показываем результат
            st.subheader("Результат:")
            st.text_area("Текст", cleaned_text, height=400)
            
            # 4. Кнопка скачивания
            st.download_button(
                label="Скачать результат (.txt)",
                data=cleaned_text,
                file_name="cleaned_text.txt",
                mime="text/plain"
            )
