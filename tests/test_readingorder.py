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
    # Draw bounding boxes
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

    # Main text
    page.insert_textbox(main_text_rect, (
        "Die Landesgeologie von swisstopo ist das Kompetenzzentrum des Bundes für die Erhebung, Analyse, Lagerung "
        "und Bereitstellung geologischer Daten von nationalem Interesse. Sie erarbeitet geologische Grundlagendaten, "
        "2D- und 3D-Modelle und leitet das unterirdische Forschungslabor Mont Terri. Das Mont Terri Projekt "
        "ist ein internationales Forschungsprojekt zur hydrogeologischen, geochemischen und "
        "geotechnischen Charakterisierung einer Tonformation (Opalinus-Ton)."
    ))

    # Side notes
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

    # Assert sort_key order (y-coordinate first, then x-coordinate)
    sort_keys = [block.sort_key for block in sorted_blocks]
    assert sort_keys == sorted(sort_keys), "Blocks are not sorted correctly by reading order."


@pytest.fixture
def table_with_gaps_doc(pdf_dir):
    # Test case inspired by Asset 7138.pdf page 52.
    doc = pymupdf.Document()
    page = doc.new_page()

    # Bounding boxes for text
    table_rect = pymupdf.Rect(20, 0, 50, 200)  # Main text column
    sidenote_rect = pymupdf.Rect(70, 60, 170, 150)

    # Main text
    page.insert_textbox(table_rect, "\n".join(["1", "2", "3", "4", "5"]) + "\n\n\n" + "\n".join(["6", "7", "8", "9", "10"]))

    # Side notes
    page.insert_textbox(sidenote_rect, "Hinweis: Swisstopo ist das Bundesamt für Landestopografie.")

    page.draw_rect(table_rect, color=(1, 0, 0), width=1)  # Red for main
    page.draw_rect(sidenote_rect, color=(0, 1, 0), width=1)
    if pdf_dir:
        doc.save(pdf_dir / "table_with_gaps.pdf")
    return doc


def test_table_with_gaps(table_with_gaps_doc):
    text = table_with_gaps_doc[0].get_text("dict")

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
        "1 2 3 4 5 6 7 8 9 10 Hinweis: Swisstopo ist das Bundesamt für Landestopografie."
    )

    assert extracted_text == expected_text, "Extracted text does not match expected reading order."


@pytest.fixture
def indentation_doc(pdf_dir):
    # Test case inspired by Asset 11806.pdf page 1 (footnote).
    doc = pymupdf.Document()
    page = doc.new_page()

    # Bounding boxes for text
    page.insert_textbox(pymupdf.Rect(0, 0, 400, 10), "This is line number one", fontsize=5)
    page.insert_textbox(pymupdf.Rect(0, 10, 400, 20), "This is line number two", fontsize=5)
    page.insert_textbox(pymupdf.Rect(12, 20, 400, 30), "Indentation line", fontsize=5)
    page.insert_textbox(pymupdf.Rect(0, 30, 400, 40), "This is line number four", fontsize=5)

    if pdf_dir:
        doc.save(pdf_dir / "indentation.pdf")
    return doc


def test_indentation(indentation_doc):
    text = indentation_doc[0].get_text("dict")

    lines = [
        _create_line(pymupdf.Rect(span['bbox']), span['text'])
        for block in text['blocks']
        for line in block['lines']
        for span in line['spans']
    ]

    sorted_blocks = sort_lines(lines)

    assert len(sorted_blocks) == 1, ("Significant indentation should not start a new block.")


def draw(page: pymupdf.Page, text: str, rect: pymupdf.Rect):
    page.insert_textbox(rect, text)
    page.draw_rect(rect, color=(0, 0, 1))


@pytest.fixture
def interval_column_paragraph_doc(pdf_dir):
    # Document with more complex layout, loosely inspired by Asset 33120 page 9
    doc = pymupdf.Document()
    page = doc.new_page()

    # Page number
    draw(
        page,
        "1",
        pymupdf.Rect(300, 0, 310, 30)
    )

    # First section
    draw(
        page,
        "10-20m",
        pymupdf.Rect(0, 40, 60, 120)
    )
    draw(
        page,
        "brauner, siltigen bis stark siltigen Feinsand mit wechselndem Grobsand-Kiesanteil (vereinzelt bis "
        "reichlich)\n"
        "brauner, siltigen bis stark siltigen Feinsand mit wechselndem Grobsand-Kiesanteil",
        pymupdf.Rect(70, 40, 300, 120)
    )
    draw(
        page,
        "20-30m",
        pymupdf.Rect(0, 125, 60, 150)
    )
    draw(
        page,
        "brauner, tonigen Kies mit viel Sand",
        pymupdf.Rect(70, 125, 300, 150)
    )

    # Paragraph
    draw(
        page,
        "Die tonig-siltigen Schwemmlehme haben eine relativ niedrige "
        "Scherfestigkeit und eine hohe Setzungsempfindlichkeit. "
        "Die sandigen Schwemmablagerungen haben wesentlich bessere Eigenschaften.",
        pymupdf.Rect(0, 155, 450, 210)
    )

    # Insert second set of depths + descriptions
    draw(page, "30-40m\n40-50m", pymupdf.Rect(0, 215, 100, 360))
    draw(page, "Humus\nSauberer Kies mit viel Sand", pymupdf.Rect(150, 215, 420, 360))

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
        "10-20m "
        "brauner, siltigen bis stark siltigen Feinsand "
        "mit wechselndem Grobsand-Kiesanteil (vereinzelt bis reichlich) "
        "brauner, siltigen bis stark siltigen Feinsand mit wechselndem Grobsand-Kiesanteil "
        "20-30m "
        "brauner, tonigen Kies mit viel Sand "
        "Die tonig-siltigen Schwemmlehme haben eine relativ niedrige "
        "Scherfestigkeit und eine hohe Setzungsempfindlichkeit. "
        "Die sandigen Schwemmablagerungen haben wesentlich bessere Eigenschaften. "
        "30-40m 40-50m "
        "1 "  # even better would be to have this page number read first, but this is ok for now
        "Humus Sauberer Kies mit viel Sand"
    )

    assert extracted_text == expected_text, "Extracted text does not match expected reading order."


