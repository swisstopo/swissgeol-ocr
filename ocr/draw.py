import pymupdf
import os

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.pdfgen.textobject import PDFTextObject

from ocr.textline import TextWord, TextLine


def draw_ocr_word(
        text: PDFTextObject,
        line_text_y: float,
        font_size: float,
        font_name: str,
        word: TextWord,
        next_word: TextWord | None,
        line: TextLine,
        line_vertical_padding: float,
        page_height: float,
        descent: float
):
    wordText = word.text
    width = word.derotated_rect.width

    word_y_middle = (word.derotated_rect.y0 + word.derotated_rect.y1) / 2
    if not line.derotated_rect.y0 + line_vertical_padding < word_y_middle < line.derotated_rect.y1 - line_vertical_padding:
        # Sometimes, especially when AWS Textract detects a slight rotation, that we subsequently ignore in the
        # TextLine._derotate_geometry() method, there are words on the "line" that actually don't belong to the
        # same line. If we detect this, we use the word's own vertical positioning.
        word_vertical_padding = (word.derotated_rect.height - font_size) / 2
        text_y = (page_height - word.derotated_rect.y1) + word_vertical_padding - descent
    else:
        if next_word is not None and next_word.derotated_rect.x0 > word.derotated_rect.x1:
            # As recommended by the OCRmyPDF implementation: render a space between this word and the next word.
            # The explicit space helps PDF viewers identify the word break, and horizontally scaling it to
            # occupy the space the between the words helps PDF viewers avoid "combiningthewordstogether".
            wordText = word.text + " "
            width = next_word.derotated_rect.x0 - word.derotated_rect.x0

        # Put everything nicely on one line, even when the individual words are detected with a slightly
        # different vertical position.
        text_y = line_text_y

    text_width = pdfmetrics.stringWidth(wordText, font_name, font_size)
    text.setHorizScale(100 * width / text_width)
    text.setTextOrigin(word.derotated_rect.x0, text_y)
    text.textOut(wordText)



def draw_ocr_text_page(
        page: pymupdf.Page,
        text_layer_path: str,
        lines: list[TextLine],
        visible: bool=False
):
    """
    Draw hidden OCR text on the page.

    Approach strongly inspired by OCRmyPDF.
    github.com/ocrmypdf/OCRmyPDF/blob/5caf654f22b7bd7c2643583956cf84397dc24156/src/ocrmypdf/hocrtransform/_hocr.py
    However, implemented here using the reportlab library instead of with pikepdf.

    The text layer is first created as a separate PDF page using reportlab (as here we have better control over
    text attributed such as horizontal spacing, compared to PyMuPDF), and afterwards overlayed onto the original PDF
    page using the PyMuPDF show_pdf_page method.
    """
    font_name = "Helvetica"

    width = page.rect.width
    height = page.rect.height
    c = canvas.Canvas(text_layer_path, pagesize=(width, height))
    c.saveState()
    current_orientation = 0
    text = c.beginText(0, 0)
    if not visible:
        text.setTextRenderMode(3)

    for line in lines:
        if line.orientation != current_orientation:
            c.drawText(text)
            c.restoreState()
            c.saveState()
            c.rotate(-line.orientation)
            current_orientation = line.orientation
            text = c.beginText(0, 0)
            if not visible:
                text.setTextRenderMode(3)

        word = None
        font_size = min(
            line.derotated_rect.height,
            line.derotated_rect.width / pdfmetrics.stringWidth(line.text, font_name, 1)
        )
        text.setFont(font_name, font_size, leading=None)

        line_vertical_padding = (line.derotated_rect.height - font_size) / 2
        descent = pdfmetrics.getDescent(font_name, fontSize=font_size)
        # invert the y coordinate, because we come from a top-down coordinate system (PyMuPDF) into a bottom-up
        # coordinate system (reportlabs).
        line_text_y = (page.rect.height - line.derotated_rect.y1) + line_vertical_padding - descent

        for next_word in line.words:
            if word is not None:
                draw_ocr_word(
                    text,
                    line_text_y,
                    font_size=font_size,
                    font_name=font_name,
                    word=word,
                    next_word=next_word,
                    line=line,
                    line_vertical_padding=line_vertical_padding,
                    page_height=page.rect.height,
                    descent=descent
                )
            word = next_word

        draw_ocr_word(
            text,
            line_text_y,
            font_size=font_size,
            font_name=font_name,
            word=word,
            next_word=None,
            line=line,
            line_vertical_padding=line_vertical_padding,
            page_height=page.rect.height,
            descent=descent
        )

    c.drawText(text)
    c.showPage()
    c.save()

    original_rotation = page.rotation
    page.set_rotation(0)
    with open(text_layer_path, 'rb') as text_layer_file:
        data = text_layer_file.read()
    # For some reason, a PyMuPDF document is not correctly closed after calling show_pdf_page with it. To avoid a
    # "too many open files" error, we first load the text layer into memory, and only then create a PyMuPDF doc from it.
    with pymupdf.Document(stream=data) as text_layer_doc:
        page.show_pdf_page(page.rect, text_layer_doc, rotate=original_rotation)
    page.set_rotation(original_rotation)
    os.remove(text_layer_path)
    return
