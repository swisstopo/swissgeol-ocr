"""Unit tests for the reading order logic."""
import pymupdf
import pytest

from ocr.readingorder import ReadingOrderGeometry


def test_textline_mustcomebefore():
    reference = ReadingOrderGeometry(pymupdf.Rect(100, 100, 200, 200))

    slight_left = ReadingOrderGeometry(pymupdf.Rect(99, 100, 199, 200))
    assert slight_left.needs_to_come_before(reference)

    slight_right = ReadingOrderGeometry(pymupdf.Rect(101, 100, 201, 200))
    assert not slight_right.needs_to_come_before(reference)

    slight_up =  ReadingOrderGeometry(pymupdf.Rect(100, 99, 200, 199))
    assert slight_up.needs_to_come_before(reference)

    slight_down = ReadingOrderGeometry(pymupdf.Rect(100, 101, 199, 201))
    assert not slight_down.needs_to_come_before(reference)

    next_column = ReadingOrderGeometry(pymupdf.Rect(200, 0, 300, 100))
    assert not next_column.needs_to_come_before(reference)

    above_right_hand_side = ReadingOrderGeometry(pymupdf.Rect(90, 90, 100, 100))
    assert above_right_hand_side.needs_to_come_before(reference)

    wide_above = ReadingOrderGeometry(pymupdf.Rect(50, 0, 400, 100))
    assert wide_above.needs_to_come_before(reference)