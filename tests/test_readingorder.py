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

    rect_left = pymupdf.Rect(0, 0, 200, 200)
    rect_right = pymupdf.Rect(240, 0, 440, 200)
    # Left-most column should be extracted first, even when the right-most column is inserted beforehand.
    page.insert_textbox(rect_right, (
        "Sie erarbeitet geologische Grundlagendaten, 2D- und 3D-Modelle und leitet das unterirdische Forschungslabor "
        "Mont Terri in St-Ursanne."
    ))
    page.insert_textbox(rect_left, (
        "Die Landesgeologie von swisstopo ist das Kompetenzzentrum des Bundes für die Erhebung, Analyse, Lagerung "
        "und Bereitstellung geologischer Daten von nationalem Interesse."
    ))
    page.draw_rect(rect_left, color = (1,0,0), width=1)
    page.draw_rect(rect_right,color =(1,0,0), width=1)

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
        "2D- und 3D-Modelle und leitet das unterirdische Forschungslabor Mont Terri in St-Ursanne."
    )

@pytest.fixture
def doc_with_header(pdf_dir):
    doc = pymupdf.Document()
    page = doc.new_page()

    # Define header and column bounding boxes
    header_left = pymupdf.Rect(70, 0, 170, 40)
    rect_left = pymupdf.Rect(0, 50, 200, 250)

    page.insert_textbox(header_left, "Header")
    page.insert_textbox(rect_left, (
        "Die Landesgeologie von swisstopo ist das Kompetenzzentrum des Bundes für die Erhebung, Analyse, Lagerung "
        "und Bereitstellung geologischer Daten von nationalem Interesse."
    ))

    page.draw_rect(header_left, color=(0, 0, 1), width=1)
    page.draw_rect(rect_left, color=(1, 0, 0), width=1)

    if pdf_dir:
        doc.save(pdf_dir / "doc_with_header.pdf")
    return doc


def test_sort_lines_with_headers(doc_with_header):
    text = doc_with_header[0].get_text("dict")
    lines = [
        _create_line(pymupdf.Rect(span['bbox']), span['text'])
        for block in text['blocks']
        for line in block['lines']
        for span in line['spans']
    ]

    sorted_blocks = sort_lines(lines)
    extracted_text = " ".join([line.text for block in sorted_blocks for line in block.lines])

    expected_text = (
        "Header Die Landesgeologie von swisstopo ist das Kompetenzzentrum des Bundes für die Erhebung, Analyse, "
        "Lagerung und Bereitstellung geologischer Daten von nationalem Interesse."
    )
    assert extracted_text == expected_text, "Extracted text does not match expected reading order."

@pytest.fixture
def single_column_with_sidenotes_doc(pdf_dir):
    doc = pymupdf.Document()
    page = doc.new_page()

    # Bounding boxes for text
    main_text_rect = pymupdf.Rect(50, 0, 250, 400)  # Main text column
    sidenote_rect_1 = pymupdf.Rect(270, 30, 370, 100)
    sidenote_rect_2 = pymupdf.Rect(270, 150, 370, 250)

    # main text
    page.insert_textbox(main_text_rect, (
        "Die Landesgeologie von swisstopo ist das Kompetenzzentrum des Bundes für die Erhebung, Analyse, Lagerung "
        "und Bereitstellung geologischer Daten von nationalem Interesse. Sie erarbeitet geologische Grundlagendaten, "
        "2D- und 3D-Modelle und leitet das unterirdische Forschungslabor Mont Terri. Das Mont Terri Projekt "
        "ist ein internationales Forschungsprojekt zur hydrogeologischen, geochemischen und "
        "geotechnischen Charakterisierung einer Tonformation (Opalinus-Ton)."
    ))

    # side notes
    page.insert_textbox(sidenote_rect_1, "Hinweis: Swisstopo ist das Bundesamt für Landestopografie.")
    page.insert_textbox(sidenote_rect_2, "Hinweis 2: Das Mont Terri Forschungslabor is in St-Ursanne.")

    page.draw_rect(main_text_rect, color=(1, 0, 0), width=1)  # Red for main
    page.draw_rect(sidenote_rect_1, color=(0, 1, 0), width=1)
    page.draw_rect(sidenote_rect_2, color=(0, 1, 0), width=1)
    if pdf_dir:
        doc.save(pdf_dir / "single_column_with_sidenotes.pdf")
    return doc


def test_sort_lines_with_sidenotes(single_column_with_sidenotes_doc):
    text = single_column_with_sidenotes_doc[0].get_text("dict")

    lines = [
        _create_line(pymupdf.Rect(span['bbox']), span['text'])
        for block in text['blocks']
        for line in block['lines']
        for span in line['spans']
    ]

    sorted_blocks = sort_lines(lines)
    extracted_text = " ".join([line.text for block in sorted_blocks for line in block.lines])

    # Expected reading order: Main text should be read first, then side notes
    expected_text = (
        "Die Landesgeologie von swisstopo ist das Kompetenzzentrum des Bundes für die Erhebung, Analyse, Lagerung "
        "und Bereitstellung geologischer Daten von nationalem Interesse. Sie erarbeitet geologische Grundlagendaten, "
        "2D- und 3D-Modelle und leitet das unterirdische Forschungslabor Mont Terri. Das Mont Terri Projekt "
        "ist ein internationales Forschungsprojekt zur hydrogeologischen, geochemischen und "
        "geotechnischen Charakterisierung einer Tonformation (Opalinus-Ton). "
        "Hinweis: Swisstopo ist das Bundesamt für Landestopografie. "
        "Hinweis 2: Das Mont Terri Forschungslabor is in St-Ursanne."
    )

    assert extracted_text == expected_text, "Extracted text does not match expected reading order."

    # assert sort_key order (y-coordinate first, then x-coordinate)
    sort_keys = [block.sort_key for block in sorted_blocks]
    assert sort_keys == sorted(sort_keys), "Blocks are not sorted correctly by reading order."

@pytest.fixture
def interval_column_paragraph_doc(pdf_dir):
    #document with more complex layout
    doc = pymupdf.Document()
    page = doc.new_page()

    # First section
    left_col_1 = pymupdf.Rect(0, 0, 100, 100)  # Depths
    right_col_1 = pymupdf.Rect(120, 0, 400, 100)  # Descriptions
    paragraph_rect = pymupdf.Rect(0, 120, 400, 200)  # Paragraph

    # second section (below the paragraph)
    left_col_2 = pymupdf.Rect(0, 220, 100, 320)  # Depths
    right_col_2 = pymupdf.Rect(120, 220, 400, 320)  # Descriptions

    page.insert_textbox(left_col_1, "10-20m\n20-30m")
    page.insert_textbox(right_col_1, "brauner, tonigen Kies mit viel Sand\n"
                                     "brauner, siltigen bis stark siltigen Feinsand "
                                     "mit wechselndem Grobsand-Kiesanteil (vereinzelt bis reichlich)")

    # Insert paragraph
    page.insert_textbox(paragraph_rect, (
        "Die tonig-siltigen Schwemmlehme haben eine relativ niedrige "
        "Scherfestigkeit und eine hohe Setzungsempfindlichkeit. "
        "Die sandigen Schwemmablagerungen haben wesentlich bessere Eigenschaften."
    ))

    # Insert second set of depths + descriptions
    page.insert_textbox(left_col_2, "30-40m\n40-50m", fontsize=15)
    page.insert_textbox(right_col_2, "Humus\nSauberer Kies mit viel Sand", fontsize=15)

    page.draw_rect(left_col_1, color=(0, 0, 1))
    page.draw_rect(right_col_1, color=(1, 0, 0))
    page.draw_rect(paragraph_rect, color=(0, 1, 0))
    page.draw_rect(left_col_2, color=(0, 0, 1))
    page.draw_rect(right_col_2, color=(1, 0, 0))

    if pdf_dir:
        doc.save(pdf_dir / "interval_column_paragraph_doc.pdf")
    return doc


def test_sort_lines_with_depths_and_paragraph(interval_column_paragraph_doc):
    text = interval_column_paragraph_doc[0].get_text("dict")

    lines = [
        _create_line(pymupdf.Rect(span['bbox']), span['text'])
        for block in text['blocks']
        for line in block['lines']
        for span in line['spans']
    ]

    # Sort the lines using reading order
    sorted_blocks = sort_lines(lines)
    extracted_text = " ".join([line.text for block in sorted_blocks for line in block.lines])

    expected_text = (
        "10-20m 20-30m "
        "brauner, tonigen Kies mit viel Sand "
        "brauner, siltigen bis stark siltigen Feinsand "
        "mit wechselndem Grobsand-Kiesanteil (vereinzelt bis reichlich) "
        "Die tonig-siltigen Schwemmlehme haben eine relativ niedrige "
        "Scherfestigkeit und eine hohe Setzungsempfindlichkeit. "
        "Die sandigen Schwemmablagerungen haben wesentlich bessere Eigenschaften. "
        "30-40m 40-50m Humus Sauberer Kies mit viel Sand"
    )

    assert extracted_text == expected_text, "Extracted text does not match expected reading order."


