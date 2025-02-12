import fitz
from mypy_boto3_textract import TextractClient as Textractor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.pdfgen.textobject import PDFTextObject

from ocr.applyocr import OCR
from ocr.readingorder import TextLine, TextWord


def process_page(
        doc: fitz.Document,
        page: fitz.Page,
        extractor: Textractor,
        tmp_path_prefix: str,
        confidence_threshold: float,
        ignore_rects: list[fitz.Rect] | None = None
):
    if ignore_rects is None:
        ignore_rects = []

    page.clean_contents()

    # create a single-page PDF document that can be modified if necessary, before being sent to AWS Textract
    textract_doc = fitz.Document()
    textract_doc.insert_pdf(doc, from_page=page.number, to_page=page.number)

    page_ocr = OCR(
        textractor=extractor,
        confidence_threshold=confidence_threshold,
        textract_doc=textract_doc,
        ignore_rects=ignore_rects,
        tmp_path_prefix=tmp_path_prefix
    )
    lines_to_draw = page_ocr.apply_ocr(clip_rect=page.rect)
    print("  {} new lines found".format(len(lines_to_draw)))
    return lines_to_draw


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
        page: fitz.Page,
        text_layer_path: str,
        lines: list[TextLine]
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
    text.setTextRenderMode(3)

    for line in lines:
        if line.orientation != current_orientation:
            c.drawText(text)
            c.restoreState()
            c.saveState()
            c.rotate(-line.orientation)
            current_orientation = line.orientation
            text = c.beginText(0, 0)
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

    with fitz.open(text_layer_path) as text_layer_doc:
        original_rotation = page.rotation
        page.set_rotation(0)
        page.show_pdf_page(page.rect, text_layer_doc, rotate=original_rotation)
        page.set_rotation(original_rotation)
    return

def is_digitally_born(page: fitz.Page) -> bool:
    bboxes = page.get_bboxlog()

    for boxType, rectangle in bboxes:
        # Empty rectangle that should be ignored occurs sometimes, e.g. SwissGeol 44191 page 37.
        if (boxType == "fill-text" or boxType == "stroke-text") and not fitz.Rect(rectangle).is_empty:
            print("  skipped")
            return True
    return False


def clean_old_ocr(page: fitz.Page):
    bboxes = page.get_bboxlog()

    counter = 0
    for boxType, rectangle in bboxes:
        if boxType == "ignore-text":
            counter += 1
            page.add_redact_annot(rectangle)
    if counter > 0:
        # Applying all redactions at once seems more reliable than applying every redact annotation separately, because
        # when removing part of some text, the remaining text sometimes seems to mysteriously move to a different
        # position on the page.
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        print("  {} boxes removed".format(counter))


def clean_old_ocr_aggressive(page: fitz.Page) -> list[fitz.Rect]:
    """
    Also cleans "fill-text" and "stroke-text" areas that are completely covered by some image.

    Returns a list of Rects that bound text that is still (potentially partially) visible, and where no OCR should be
    applied.
    """
    bboxes = page.get_bboxlog()

    possibly_visible_text = []
    invisible_text = []
    for boxType, rectangle in bboxes:
        rect = fitz.Rect(rectangle)
        if boxType == "ignore-text":
            # Some digitally-born documents (e.g. ZH 267124198-bp.pdf) draw the text using fill-path elements and then
            # add `ignore-text` to make the text searchable/selectable. We don't want to remove these.
            if all(not rect.intersects(visible) for visible in possibly_visible_text):
                invisible_text.append(rect)
        # Empty rectangle that should be ignored occurs sometimes, e.g. SwissGeol 44191 page 37.
        if (boxType == "fill-text" or boxType == "stroke-text" or boxType == "fill-path") and not rect.is_empty:
            possibly_visible_text.append(rect)
        if boxType == "fill-image":
            invisible_text.extend([text_rect for text_rect in possibly_visible_text if rect.contains(text_rect)])
            possibly_visible_text = [text_rect for text_rect in possibly_visible_text if not rect.contains(text_rect)]

    counter = 0
    for rect in invisible_text:
        counter += 1
        page.add_redact_annot(rect)
    if counter > 0:
        # Applying all redactions at once seems more reliable than applying every redact annotation separately, because
        # when removing part of some text, the remaining text sometimes seems to mysteriously move to a different
        # position on the page.
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        print("  {} boxes removed".format(counter))

    if len(possibly_visible_text):
        print("  {} boxes preserved".format(len(possibly_visible_text)))

    return possibly_visible_text

