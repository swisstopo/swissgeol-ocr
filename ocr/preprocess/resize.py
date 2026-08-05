import logging

import pymupdf


def resize_page(doc: pymupdf.Document, page_index: int):
    src_page = doc[page_index]
    page_rect = src_page.rect
    src_page_rotation = src_page.rotation
    page_is_narrow = page_rect.width < 144
    if page_is_narrow or src_page.rotation != 0:
        if page_is_narrow:
            logging.info("  Resizing/enlarging page with small dimensions {:.2f}x{:.2f}.".format(page_rect.width, page_rect.height))
            factor = 20
        else:
            logging.info("  Resetting page rotation from {} to 0.".format(src_page.rotation))
            factor = 1
        src_page.set_rotation(0)

        replace_page(doc, page_index, scale=factor, rotate=-src_page_rotation)

def replace_page(doc: pymupdf.Document, page_index: int, scale: float=1.0, rotate: float=0.0):
    src_page = doc[page_index]
    page_rect = src_page.rect
    new_page_rect = page_rect * pymupdf.Matrix(scale, scale).prerotate(rotate)

    # Use a tmp doc to avoid the constraint "source document must not equal target" for show_pdf_page
    tmp_doc = pymupdf.Document()
    tmp_page = tmp_doc.new_page(0, new_page_rect.width, new_page_rect.height)
    tmp_page.show_pdf_page(tmp_page.rect, doc, page_index, rotate=rotate)

    new_page = doc.new_page(page_index, tmp_page.rect.width, tmp_page.rect.height)
    new_page.show_pdf_page(tmp_page.rect, tmp_doc, 0)

    # We first insert the new page and only then delete the old one; this fixes an issue with 28957.pdf, where
    # we encountered the error "pymupdf.mupdf.FzErrorFormat: code=7: kid not found in parent's kids array".
    doc.delete_page(page_index + 1)
