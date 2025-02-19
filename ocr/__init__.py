import os
import subprocess

import pymupdf
from pymupdf import mupdf
from pymupdf.mupdf import PDF_ENCRYPT_KEEP
from pathlib import Path
from mypy_boto3_textract import TextractClient as Textractor

from ocr.crop import crop_images, replace_jpx_images
from ocr.resize import resize_page
from ocr.util import process_page, clean_old_ocr, is_digitally_born, draw_ocr_text_page, clean_old_ocr_aggressive


def process(
        input_path: Path,
        output_path: Path,
        tmp_dir: Path,
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
    except (ValueError, mupdf.FzErrorArgument, mupdf.FzErrorFormat) as e:
        gs_preprocess_path = tmp_dir / "gs.pdf"
        print(f"Encountered {e.__class__.__name__}: {e}. Trying Ghostscript preprocessing.")
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
        in_path: Path,
        out_path: Path,
        tmp_dir: Path,
        textractor: Textractor,
        confidence_threshold: float,
        use_aggressive_strategy: bool,
):
    tmp_out_path = os.path.join(tmp_dir, f"output.incremental.pdf")

    in_doc = pymupdf.open(in_path)
    out_doc = pymupdf.open(in_path)

    os.makedirs(tmp_dir, exist_ok=True)

    in_page_count = in_doc.page_count

    out_doc.save(tmp_out_path, garbage=3, deflate=True)
    out_doc.close()
    out_doc = pymupdf.open(tmp_out_path)
    for page_index, new_page in enumerate(iter(in_doc)):
        page_number = page_index + 1
        print(f"{os.path.basename(in_path)}, page {page_number}/{in_page_count}")

        digitally_born = is_digitally_born(in_doc[page_index])

        if not digitally_born:
            # We reload the page using doc[page_index] every time before calling page.get_image_info(), instead of
            # re-using the same page object, as the latter can lead to strange behaviour (xref=0 and outdated values
            # from the second page.get_image_info() call). This is because the result of the page.get_image_info()
            # call is cached on the Page object, and this cache is not autmoatically cleared when modifying some of the
            # images (e.g. calling page.replace_image()). This has been reported as a bug on the PyMuPDF GitHub repo:
            # https://github.com/pymupdf/PyMuPDF/issues/4303
            resize_page(in_doc, out_doc, page_index)
            replace_jpx_images(out_doc, page_index)
            crop_images(out_doc, page_index)

        new_page = out_doc[page_index]

        if use_aggressive_strategy:
            ignore_rects = clean_old_ocr_aggressive(new_page)
        else:
            if not digitally_born:
                clean_old_ocr(new_page)
                ignore_rects = []
            else:
                print(" Skipping digitally-born page.")
                continue
        tmp_path_prefix = os.path.join(tmp_dir, f"page{page_number}")
        text_layer_path = os.path.join(tmp_dir, f"page{page_number}.pdf")
        lines_to_draw = process_page(out_doc, new_page, textractor, tmp_path_prefix, confidence_threshold, ignore_rects)
        draw_ocr_text_page(new_page, text_layer_path, lines_to_draw)
        out_doc.save(tmp_out_path, incremental=True, encryption=PDF_ENCRYPT_KEEP)

    out_doc.close()
    in_doc.close()
    out_doc = pymupdf.open(tmp_out_path)
    out_doc.save(out_path, garbage=3, deflate=True, use_objstms=1)
    out_doc.close()

    # Verify that we can read the written document, and that it still has the same number of pages. Some corrupt input
    # documents might lead to an empty or to a corrupt output document, sometimes even without throwing an error. (See
    # LGD-283.) This check should detect such cases.
    doc = pymupdf.open(out_path)
    out_page_count = doc.page_count
    if in_page_count != out_page_count:
        raise ValueError(
            "Output document contains {} pages instead of {}".format(out_page_count, in_page_count)
        )
    doc.close()
