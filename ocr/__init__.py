import os
import subprocess

import fitz
from mypy_boto3_textract import TextractClient as Textractor
from pymupdf.mupdf import PDF_ENCRYPT_KEEP

from ocr.crop import crop_images
from ocr.resize import resize_page
from ocr.util import process_page, clean_old_ocr, new_ocr_needed, draw_ocr_text_page, clean_old_ocr_aggressive


def process(
        input_path: str,
        output_path: str,
        tmp_dir: str,
        textractor: Textractor,
        confidence_threshold: float,
        use_aggressive_strategy: bool,
):
    try:
        process_pdf(
            input_path,
            output_path,
            tmp_dir,
            textractor,
            confidence_threshold,
            use_aggressive_strategy
        )
    except ValueError as e:
        gs_preprocess_path = os.path.join(tmp_dir, "gs.pdf")
        print(f"Encountered ValueError: {e}. Trying Ghostscript preprocessing.")
        subprocess.call([
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/default",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            "-sOutputFile={}".format(gs_preprocess_path),
            input_path,
        ])
        process_pdf(
            gs_preprocess_path,
            output_path,
            tmp_dir,
            textractor,
            confidence_threshold,
            use_aggressive_strategy,
        )


def process_pdf(
        in_path: str,
        out_path: str,
        tmp_dir: str,
        textractor: Textractor,
        confidence_threshold: float,
        use_aggressive_strategy: bool,
):
    tmp_out_path = os.path.join(tmp_dir, f"output.pdf")

    in_doc = fitz.open(in_path)
    out_doc = fitz.open(in_path)

    os.makedirs(tmp_dir, exist_ok=True)

    in_page_count = in_doc.page_count
    print(f"{in_page_count} pages")

    out_doc.save(tmp_out_path, garbage=3, deflate=True)
    out_doc.close()
    out_doc = fitz.open(tmp_out_path)
    for page_index, new_page in enumerate(iter(in_doc)):
        page_number = page_index + 1
        print(f"Page {page_number}")

        new_page = resize_page(in_doc, out_doc, page_index)
        crop_images(new_page, out_doc)
        if use_aggressive_strategy:
            ignore_rects = clean_old_ocr_aggressive(new_page)
        else:
            if new_ocr_needed(new_page):
                clean_old_ocr(new_page)
                ignore_rects = []
            else:
                continue
        tmp_path_prefix = os.path.join(tmp_dir, f"page{page_number}")
        text_layer_path = os.path.join(tmp_dir, f"page{page_number}.pdf")
        lines_to_draw = process_page(out_doc, new_page, textractor, tmp_path_prefix, confidence_threshold, ignore_rects)
        draw_ocr_text_page(new_page, text_layer_path, lines_to_draw)
        out_doc.save(tmp_out_path, incremental=True, encryption=PDF_ENCRYPT_KEEP)

    out_doc.close()
    out_doc = fitz.open(tmp_out_path)
    out_doc.save(out_path, garbage=3, deflate=True)
    in_doc.close()
    out_doc.close()

    # Verify that we can read the written document, and that it still has the same number of pages. Some corrupt input
    # documents might lead to an empty or to a corrupt output document, sometimes even without throwing an error. (See
    # LGD-283.) This check should detect such cases.
    doc = fitz.open(out_path)
    out_page_count = doc.page_count
    if in_page_count != out_page_count:
        raise ValueError(
            "Output document contains {} pages instead of {}".format(out_page_count, in_page_count)
        )
    doc.close()
