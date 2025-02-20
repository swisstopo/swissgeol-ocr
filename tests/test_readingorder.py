"""Unit tests for the reading order logic.

In order to easily visualise the different layouts that are tested in this file, run pytest with the additional option
  pytest --pdf-dir=tmp
and all layouts that are tested will be written as PDF files to the tmp/ directory.
"""
import pymupdf
import pytest

from ocr.readingorder import sort_lines, TextLine

def _create_line(rect: pymupdf.Rect, text: str) -> TextLine:
    return TextLine(rect=rect, text=text, derotated_rect=pymupdf.Rect(), orientation=0, confidence=1, words=[])

@pytest.fixture
def two_columns_doc(pdf_dir):
    doc = pymupdf.Document()
    page = doc.new_page()
    # Left-most column should be extracted first, even when the right-most column is inserted beforehand.
    page.insert_textbox(pymupdf.Rect(240, 0, 440, 200), (
        "Sie erarbeitet geologische Grundlagendaten, 2D- und 3D-Modelle und leitet das unterirdische Forschungslabor "
        "Mont Terri in St-Ursanne."
    ))
    page.insert_textbox(pymupdf.Rect(0, 0, 200, 200), (
        "Die Landesgeologie von swisstopo ist das Kompetenzzentrum des Bundes für die Erhebung, Analyse, Lagerung "
        "und Bereitstellung geologischer Daten von nationalem Interesse."
    ))
    if pdf_dir:
        doc.save(pdf_dir / "two_columns_doc.pdf")
    return doc

def test_sort_lines(two_columns_doc):
    text = two_columns_doc[0].get_text("dict")
    lines = [
        _create_line(pymupdf.Rect(span['bbox']), span['text'])
        for block in text['blocks']
        for line in block['lines']
        for span in line['spans']
    ]
    text = " ".join([line.text for block in sort_lines(lines) for line in block.lines])
    assert text == (
        "Die Landesgeologie von swisstopo ist das Kompetenzzentrum des Bundes für die Erhebung, Analyse, Lagerung "
        "und Bereitstellung geologischer Daten von nationalem Interesse. Sie erarbeitet geologische Grundlagendaten, "
        "2D- und 3D-Modelle und leitet das unterirdische Forschungslabor Mont Terri in St-Ursanne. "
    )
