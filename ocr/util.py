import pymupdf


def is_digitally_born(page: pymupdf.Page) -> bool:
    bboxes = page.get_bboxlog()

    for boxType, rectangle in bboxes:
        # Empty rectangle that should be ignored occurs sometimes, e.g. SwissGeol 44191 page 37.
        if (boxType == "fill-text" or boxType == "stroke-text") and not pymupdf.Rect(rectangle).is_empty:
            return True
    return False


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
