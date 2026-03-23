import io

import pymupdf

import logging


def preprocess(doc: pymupdf.Document):
    # Some PDF files have "Pages" nodes with no children in their page tree. (One example is 268124319-bp from the ZH
    # boreholes dataset.) While the PDF specification does not explicitly prohibit this, it can cause problems in some
    # PDF viewers, especially if the same empty Pages node is referenced several times. The error message "Too many
    # pages in Page tree." from Ghostscript is an indication that there might be empty pages nodes in the PDF document.
    # (See also LGD-933.)
    #
    # If we detect this, then we force the recreation of the PDF page tree by calling doc.select() with a full
    # selection of all pages in the document.
    if has_empty_nodes_in_pages_tree(doc):
        logging.info("Empty nodes in page tree detected. Recreating page tree.")
        # select all pages
        doc.select(range(doc.page_count))


def _parse_kids_array(value: str) -> list[int]:
    trimmed_value = value[1:-1]
    if not trimmed_value:
        return []
    xref_values = trimmed_value.split(" ")[::3]
    return [int(value) for value in xref_values if value.isdigit()]


def _has_empty_pages_nodes(doc: pymupdf.Document, xref: int) -> bool:
    if doc.xref_get_key(xref, "Type")[1] == "/Pages":
        kids_type, kids_values = doc.xref_get_key(xref, "Kids")
        if kids_type == 'array':
            kids_xrefs = _parse_kids_array(kids_values)
            if not kids_xrefs:
                return True
            return any(
                _has_empty_pages_nodes(doc, kid_xref)
                for kid_xref in kids_xrefs
            )
    return False


def has_empty_nodes_in_pages_tree(doc: pymupdf.Document) -> bool:
    catalog = doc.pdf_catalog()  # get xref of the /Catalog

    pages_root_xref = int(doc.xref_get_key(catalog, "Pages")[1].split(' ')[0])
    return _has_empty_pages_nodes(doc, pages_root_xref)
