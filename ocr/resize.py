import fitz


def resize_page(in_doc: fitz.Document, out_doc: fitz.Document, page_index: int) -> fitz.Page:
    src_page = in_doc[page_index]
    page_rect = src_page.rect
    src_page_rotation = src_page.rotation
    if page_rect.width < 144 or src_page.rotation != 0:
        if page_rect.width < 144:
            print("  Resizing/enlarging page with small dimensions {:.2f}x{:.2f}.".format(page_rect.width, page_rect.height))
            factor = 20
        else:
            print("  Resetting page rotation from {} to 0.".format(src_page.rotation))
            factor = 1
        out_doc.delete_page(page_index)
        src_page.set_rotation(0)
        new_page = out_doc.new_page(page_index, page_rect.width * factor, page_rect.height * factor)
        new_page.show_pdf_page(new_page.rect, in_doc, page_index, rotate=-src_page_rotation)
    return out_doc[page_index]
