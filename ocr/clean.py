import pymupdf

def clean_old_ocr(page: pymupdf.Page):
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
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        print("  {} boxes removed".format(counter))


def clean_old_ocr_aggressive(page: pymupdf.Page) -> list[pymupdf.Rect]:
    """
    Also cleans "fill-text" and "stroke-text" areas that are completely covered by some image.

    Returns a list of Rects that bound text that is still (potentially partially) visible, and where no OCR should be
    applied.
    """
    bboxes = page.get_bboxlog()

    possibly_visible_text = []
    invisible_text = []
    for boxType, rectangle in bboxes:
        rect = pymupdf.Rect(rectangle)
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
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        print("  {} boxes removed".format(counter))

    if len(possibly_visible_text):
        print("  {} boxes preserved".format(len(possibly_visible_text)))

    return possibly_visible_text