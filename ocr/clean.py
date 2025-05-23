import pymupdf
from ocr.mask import Mask
from ocr.util import fast_intersection


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


def clean_old_ocr_aggressive(page: pymupdf.Page) -> Mask:
    """
    Also cleans "fill-text" and "stroke-text" areas that are completely covered by some image.

    Returns a "mask", a 2D matrix with dimensions corresponding to page.rect (rounded to the nearest integer). An entry in
    the mask equals 1 if on that location on the page there is text that is still (potentially partially) visible, and
    where no OCR should be applied. Otherwise, the value will be 0, and OCR can be (re)applied here.
    """
    bboxes = page.get_bboxlog()

    mask = Mask(page)
    possibly_visible_text = set()
    invisible_text = set()

    for boxType, rectangle in bboxes:
        rect = pymupdf.Rect(rectangle)
        if boxType == "ignore-text":
            # Some digitally-born documents (e.g. ZH 267124198-bp.pdf) draw the text using fill-path elements and then
            # add `ignore-text` to make the text searchable/selectable. We don't want to remove these.
            if not mask.intersects(rect):
                invisible_text.add(rect)
        # Empty rectangle that should be ignored occurs sometimes, e.g. SwissGeol 44191 page 37.
        if (boxType == "fill-text" or boxType == "stroke-text" or boxType == "fill-path") and not rect.is_empty:
            mask.add_rect(rect)
            possibly_visible_text.add(rect)
        if boxType == "fill-image":
            to_be_removed = set()
            for text_rect in possibly_visible_text:
                if rect.contains(text_rect):
                    invisible_text.add(text_rect)
                    to_be_removed.add(text_rect)
            for text_rect in to_be_removed:
                possibly_visible_text.remove(text_rect)
            mask.remove_rect(rect)

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

    return mask