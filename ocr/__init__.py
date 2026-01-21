import dataclasses
import logging
import os
import subprocess
from pathlib import Path

import pymupdf
from mypy_boto3_textract import TextractClient
from pymupdf import mupdf

from ocr.mask import Mask
from ocr.applyocr import process_page
from ocr.clean import clean_old_ocr, clean_old_ocr_aggressive
from ocr.crop import crop_images, replace_jpx_images
from ocr.draw import draw_ocr_text_page
from ocr.resize import resize_page
from ocr.util import is_digitally_born
from PIL import Image


# Avoid "could be decompression bomb DOS attack" error, because this gives false positives on high-resolution scans
Image.MAX_IMAGE_PIXELS = None

@dataclasses.dataclass
class ProcessResult:
    number_of_pages: int | None


@dataclasses.dataclass
class Processor:
    input_path: Path
    output_path: Path
    debug_page: int | None
    tmp_dir: Path
    textract_client: TextractClient
    confidence_threshold: float
    use_aggressive_strategy: bool

    def process(self):
        try:
            number_of_pages = self.process_pdf(self.input_path)
        except (ValueError, mupdf.FzErrorArgument, mupdf.FzErrorFormat) as e:
            gs_preprocess_path = self.tmp_dir / "gs.pdf"
            logging.info(f"Encountered {e.__class__.__name__}: {e}. Trying Ghostscript preprocessing.")
            subprocess.call([
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                "-dPDFSETTINGS=/default",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                "-sOutputFile={}".format(gs_preprocess_path),
                self.input_path,
            ])
            number_of_pages = self.process_pdf(gs_preprocess_path)

        return ProcessResult(number_of_pages)

    def process_pdf(self, in_path: Path) -> int | None:
        """
        Processes a given PDF

        Returns:
            int|None: number of pages in the output document if possible
        """
        doc = pymupdf.open(in_path)
        in_page_count = doc.page_count

        for page_index, _ in enumerate(iter(doc)):
            page_number = page_index + 1
            if not self.debug_page or page_number == self.debug_page:
                logging.info(f"{os.path.basename(in_path)}, page {page_number}/{in_page_count}")
                self.process_page(page_index, doc, add_debug_page=bool(self.debug_page))
                pymupdf.TOOLS.store_shrink(100)

        if self.debug_page:
            # only keep the debug page in its two versions (original + text-only)
            doc.delete_pages(range(0, self.debug_page - 1))
            doc.delete_pages(range(2, doc.page_count))

        doc.ez_save(self.output_path)
        doc.close()

        # Verify that we can read the written document, and that it still has the same number of pages. Some corrupt input
        # documents might lead to an empty or to a corrupt output document, sometimes even without throwing an error. (See
        # LGD-283.) This check should detect such cases.
        doc = pymupdf.open(self.output_path)
        if not self.debug_page:
            out_page_count = doc.page_count
            if in_page_count != out_page_count:
                raise ValueError(
                    "Output document contains {} pages instead of {}".format(out_page_count, in_page_count)
                )
        doc.close()

        return in_page_count if in_page_count > 0 else None

    def process_page(
        self,
        page_index: int,
        doc: pymupdf.Document,
        add_debug_page: bool = False
    ):
        page_number = page_index + 1
        digitally_born = is_digitally_born(doc[page_index])

        if not digitally_born:
            # We reload the page using doc[page_index] every time before calling page.get_image_info(), instead of
            # re-using the same page object, as the latter can lead to strange behaviour (xref=0 and outdated values
            # from the second page.get_image_info() call). This is because the result of the page.get_image_info()
            # call is cached on the Page object, and this cache is not autmoatically cleared when modifying some of the
            # images (e.g. calling page.replace_image()). This has been reported as a bug on the PyMuPDF GitHub repo:
            # https://github.com/pymupdf/PyMuPDF/issues/4303
            resize_page(doc, page_index)
            replace_jpx_images(doc, page_index)
            crop_images(doc, page_index)

        new_page = doc[page_index]

        mask = Mask(new_page)
        if self.use_aggressive_strategy:
            mask = clean_old_ocr_aggressive(new_page)
        else:
            if not digitally_born:
                clean_old_ocr(new_page)
            else:
                logging.info(" Skipping digitally-born page.")
                return
        tmp_path_prefix = os.path.join(self.tmp_dir, f"page{page_number}")
        lines_to_draw = process_page(doc, new_page, self.textract_client, tmp_path_prefix,
                                     self.confidence_threshold, mask)

        text_layer_path = os.path.join(self.tmp_dir, f"page{page_number}.pdf")
        draw_ocr_text_page(new_page, text_layer_path, lines_to_draw)
        if add_debug_page:
            debug_page = doc.new_page(new_page.number + 1, new_page.rect.width, new_page.rect.height)
            draw_ocr_text_page(debug_page, text_layer_path, lines_to_draw, visible=True)

        # Only call saveIncr() when something actually changed, not for digitally-born pages. Otherwise, files like
        # Asset 39713.pdf cause problems.
        doc.saveIncr()
