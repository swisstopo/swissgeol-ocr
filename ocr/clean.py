import pymupdf
from ocr.mask import Mask


def find_old_ocr_rects(page: pymupdf.Page) -> list[pymupdf.Rect]:
    bboxes = page.get_bboxlog()
    """Return a list of bounding boxes for existing OCR text.

    This includes bounding boxes of type "ignore-text", as well as bounding boxes of type 
    "fill-text" or "stroke-text" on the condition that they are all covered by a single image.

    If the page appears to be digitally-born, then an empty list is returned (and even bounding
    boxes of type "ignore-text" are not returned).

    The exception deals with cases such as:
    - XWQE17I800_bp_19851224_Tiefenbrunnen-2.pdf (deep wells), page 2
    - MTPE17I800_bp_19770101_Lostorf-3.pdf (deep wells), pages 1-8
    """
    ignore_text_rects = []
    visible_text_rects = []
    text_bbox_union = pymupdf.Rect()
    all_text_covered = False

    for boxType, coordinates in bboxes:
        rectangle = pymupdf.Rect(coordinates)
        # Empty rectangle that should be ignored occurs sometimes, e.g. SwissGeol 44191 page 37.
        if (boxType == "fill-text" or boxType == "stroke-text") and not rectangle.is_empty:
            all_text_covered = False
            text_bbox_union = text_bbox_union | rectangle
            visible_text_rects.append(rectangle)
        if boxType == "fill-image" or boxType == "fill-imgmask":
            if rectangle.contains(text_bbox_union):
                all_text_covered = True
        if boxType == "ignore-text":
            ignore_text_rects.append(rectangle)

    if all_text_covered:
        return visible_text_rects + ignore_text_rects
    else:
        return ignore_text_rects

def clean_old_ocr(page: pymupdf.Page):
    rects = find_old_ocr_rects(page)
    if rects:
        for rectangle in rects:
            page.add_redact_annot(rectangle)

        # Applying all redactions at once seems more reliable than applying every redact annotation separately, because
        # when removing part of some text, the remaining text sometimes seems to mysteriously move to a different
        # position on the page.
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        print("  {} boxes removed".format(len(rects)))


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
            else:
                # In some scanned documents, every word is put into a separate image in the PDF file, e.g. Zurich
                # borehole profile 269126062-bp.pdf. The word's image might be slightly smaller than the bounding box
                # of the word as detected by OCR. For this reason, we check again using a version of the word's
                # bounding box that is shrunk by 10% on every side, and we also allow up to 20% overlap with the mask.
                shrunk_rect = pymupdf.Rect(
                    rect.x0 + 0.1 * rect.width,
                    rect.y0 + 0.1 * rect.height,
                    rect.x1 - 0.1 * rect.width,
                    rect.y1 - 0.1 * rect.height
                )
                if mask.coverage_ratio(shrunk_rect) < 0.2:
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