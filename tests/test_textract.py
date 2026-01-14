"""Unit tests for textract."""
from ocr.textract import clip_rects
from pymupdf import Rect

def test_clip_rects():
    small = Rect(0, 0, 1000, 1000)
    assert clip_rects(small) == [small]

    large = Rect(0, 0, 3000, 3000)
    top_left = Rect(0, 0, 2000, 2000)
    top_right = Rect(1600, 0, 3000, 2000)
    bottom_left = Rect(0, 1600, 2000, 3000)
    bottom_right = Rect(1600, 1600, 3000, 3000)
    assert clip_rects(large) == [large, top_left, bottom_left, top_right, bottom_right]

    wide = Rect(0, 0, 5000, 200)
    left = Rect(0, 0, 2000, 200)
    middle = Rect(1600, 0, 3600, 200)
    right = Rect(3200, 0, 5000, 200)
    assert clip_rects(wide) == [wide, left, middle, right]

    tall = Rect(0, 0, 200, 5000)
    top = Rect(0, 0, 200, 2000)
    middle = Rect(0, 1600, 200, 3600)
    bottom = Rect(0, 3200, 200, 5000)
    assert clip_rects(tall) == [tall, top, middle, bottom]

