import pymupdf


def is_digitally_born(page: pymupdf.Page) -> bool:
    bboxes = page.get_bboxlog()
    """Returns whether the page is identified as digitally born.
    
    A page is digitally born as soon as it has a bounding boxes of type "fill-text" or "stroke-text"
    unless all such boxes are covered by a single image.
    
    The exception deals with cases such as:
    - XWQE17I800_bp_19851224_Tiefenbrunnen-2.pdf (deep wells), page 2
    - MTPE17I800_bp_19770101_Lostorf-3.pdf (deep wells), pages 1-8
    where text from OCR is actually defined as "fill-text" (instead of "ignore-text") and then covered
    by the image.
    
    Additionally, a page that does not have any image, is always identified as digitally born. 
    """
    text_bbox_union = pymupdf.Rect()
    all_text_covered = False
    has_image = False

    for boxType, coordinates in bboxes:
        rectangle = pymupdf.Rect(coordinates)
        # Empty rectangle that should be ignored occurs sometimes, e.g. SwissGeol 44191 page 37.
        if (boxType == "fill-text" or boxType == "stroke-text") and not rectangle.is_empty:
            all_text_covered = False
            text_bbox_union = text_bbox_union | rectangle
        if boxType == "fill-image":
            has_image = True
            if rectangle.contains(text_bbox_union):
                all_text_covered = True

    return not (has_image and (text_bbox_union.is_empty or all_text_covered))


def x_overlap(rect1: pymupdf.Rect, rect2: pymupdf.Rect) -> float:  # noqa: D103
    """Calculate the x overlap between two rectangles.

    Args:
        rect1 (pymupdf.Rect): First rectangle.
        rect2 (pymupdf.Rect): Second rectangle.

    Returns:
        float: The x overlap between the two rectangles.
    """
    if (rect1.x0 < rect2.x1) and (rect2.x0 < rect1.x1):
        return min(rect1.x1, rect2.x1) - max(rect1.x0, rect2.x0)
    else:
        return 0

def fast_intersection(rect1: pymupdf.Rect, rect2: pymupdf.Rect) -> bool:
    """Returns whether there is a non-empty intersection between both given rectangles.

    A significantly faster implementation compared to the pymupdf method Rect.intersects().
    See also https://github.com/pymupdf/PyMuPDF/issues/4527.

    Args:
        rect1 (pymupdf.Rect): First rectangle.
        rect2 (pymupdf.Rect): Second rectangle.

    Returns:
        bool: True if there is a non-empty intersection between the two rectangles.
    """
    return (rect1.x0 < rect2.x1) and (rect2.x0 < rect1.x1) and (rect1.y0 < rect2.y1) and (rect2.y0 < rect1.y1)
