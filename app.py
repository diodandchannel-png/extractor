import streamlit as st
from pypdf import PdfReader

# Попытка импорта для OCR
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    OCR_OK = True
except ImportError:
    OCR_OK = False

# --- 1. ФУНКЦИЯ ОЧИСТКИ ---
def clean_text(raw_text):
    lines = raw_text.split('\n')
    res = ""
    buf = ""
    for line in lines:
        s = line.strip()
        if not s or s.isdigit(): continue

        is_new = s[0].isupper() if s else False
        is_end = buf.endswith(('.', '!', '?'))

        if (is_end and is_new) and buf:
            res += buf + "\n\n"
            buf = s
        else:
            if buf.endswith('-'): buf = buf[:-1] + s
            else: buf += " " + s if buf else s
    return res + buf

# --- 2. ЗАГРУЗКА PDF ---
def get_pdf_content(file, pages, ocr):
    text = ""
    # Если OCR включен И библиотеки найдены
    if ocr and OCR_OK:
        try:
            imgs = convert_from_bytes(file.read())
            file.seek(0)
            for i in pages:
                if i < len(imgs):
                    text += pytesseract.image_to_string(imgs[i], lang='rus+eng') + "\n"
        except Exception as e:
            return f"Ошибка OCR: {e}. Попробуйте отключить галочку OCR."
    else:
        # Обычный режим (или если OCR недоступен)
        reader = PdfReader(file)
        for i in pages:
            if i < len(reader.pages):
                t = reader.pages[i].extract_text()
                text += t if t else ""
    return text

# --- 3. ИНТЕРФЕЙС ---
st.set_page_config(page_title="PDF Tool")
st.title("PDF Master")

f = st.file_uploader("PDF файл", type="pdf")

if f:
    reader = PdfReader(f)
    n_pages = len(reader.pages)
    st.write(f"Страниц: {n_pages}")

    # Выбор режима
    mode = st.radio("Режим:", ["Страницы", "Фразы"], horizontal=True)

    # Настройки
    p1 = st.number_input("От стр", 1, n_pages, 1)
    p2 = st.number_input("До стр", 1, n_pages, n_pages)

    ph1 = ""
    ph2 = ""
    if mode == "Фразы":
        ph1 = st.text_input("Начало (фраза)")
        ph2 = st.text_input("Конец (фраза)")

    # Если библиотеки OCR не найдены, галочка будет неактивна или с пометкой
    ocr_label = "OCR (скан)" if OCR_OK else "OCR (недоступно на сервере)"
    use_ocr = st.checkbox(ocr_label, disabled=not OCR_OK)

    st.divider()
    c1, c2 = st.columns([3, 1])

    do_run = False
    do_reset = False

    with c1:
        if st.button("СТАРТ", type="primary"):
            do_run = True

    with c2:
        if st.button("СБРОС"):
            do_reset = True

    if do_reset:
        st.rerun()

    if do_run:
        pgs = [i-1 for i in range(p1, p2+1)]
        # Добавляем спиннер, чтобы было видно процесс
        with st.spinner("Обработка..."):
            raw = get_pdf_content(f, pgs, use_ocr)

        if not raw:
            st.error("Пусто! Возможно, это картинка без текстового слоя.")
        elif "Ошибка OCR" in raw:
             st.error(raw)
        else:
            final = clean_text(raw)

            if mode == "Фразы" and ph1 and ph2:
                i1 = final.find(ph1)
                i2 = final.find(ph2, i1)
                if i1 != -1 and i2 != -1:
                    final = final[i1 : i2 + len(ph2)]
                else:
                    final = "Фразы не найдены."

            st.text_area("Итог", final, height=400)
            chars = len(final.replace(" ", ""))
            st.info(f"Зн: {chars} | A4: {chars/1725:.2f}")