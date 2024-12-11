import boto3
from pymupdf import mupdf
from textractor import Textractor

from util.source import S3AssetSource, FileAssetSource
from util.target import S3AssetTarget, FileAssetTarget, AssetTarget
from util.util import process_page, clean_old_ocr, new_ocr_needed, draw_ocr_text_page, clean_old_ocr_aggressive
from util.crop import crop_images
from util.resize import resize_page
from pathlib import Path
from dotenv import dotenv_values
import os
import fitz
import subprocess
import sys


def load_target(config):
    if config["OCR_OUTPUT_TYPE"] == "S3":
        s3_session = boto3.Session(profile_name=config["OCR_OUTPUT_AWS_PROFILE"])
        s3 = s3_session.resource('s3')
        return S3AssetTarget(
            s3_bucket=s3.Bucket(config["OCR_OUTPUT_S3_BUCKET"]),
            s3_prefix=config["OCR_OUTPUT_S3_PREFIX"],
            output_path_fn=lambda filename: Path(sys.path[0], "tmp", "new_" + filename),
            do_cleanup=(config["OCR_OUTPUT_CLEANUP_TMP_FILES"] == "TRUE")
        )
    elif config["OCR_OUTPUT_TYPE"] == "path":
        return FileAssetTarget(
            out_path=Path(config["OCR_OUTPUT_PATH"])
        )
    else:
        print("No OCR_OUTPUT_TYPE specified.")
        sys.exit(1)


def load_source(config, target: AssetTarget):
    if config["OCR_INPUT_IGNORE_EXISTING"] == "TRUE":
        ignore_filenames = target.existing_filenames()
        print("Found {} existing objects in output path.".format(len(ignore_filenames)))
    else:
        ignore_filenames = []

    if config["OCR_INPUT_TYPE"] == "S3":
        s3_session = boto3.Session(profile_name=config["OCR_INPUT_AWS_PROFILE"])
        s3 = s3_session.resource('s3')

        return S3AssetSource(
            s3_bucket=s3.Bucket(config["OCR_INPUT_S3_BUCKET"]),
            s3_prefix=config["OCR_INPUT_S3_PREFIX"],
            allow_override=False,
            input_path_fn=lambda filename: Path(sys.path[0], "tmp", filename),
            do_cleanup=(config["OCR_INPUT_CLEANUP_TMP_FILES"] == "TRUE"),
            ignore_filenames=ignore_filenames
        )
    elif config["OCR_INPUT_TYPE"] == "path":
        return FileAssetSource(
            in_path=Path(config["OCR_INPUT_PATH"]),
            ignore_filenames=ignore_filenames
        )
    else:
        print("No OCR_INPUT_TYPE specified.")
        sys.exit(1)


def process(filename, in_path, out_path, extractor, confidence_threshold, aggressive_strategy):

    in_doc = fitz.open(in_path)
    out_doc = fitz.open(in_path)

    in_page_count = in_doc.page_count
    for page_index, new_page in enumerate(out_doc):
        page_number = page_index + 1
        print(f"{filename}, page {page_number}/{in_page_count}")

        new_page = resize_page(in_doc, out_doc, page_index)
        # crop_images(new_page, out_doc)
        if aggressive_strategy:
            ignore_rects = clean_old_ocr_aggressive(new_page)
        else:
            if new_ocr_needed(new_page):
                clean_old_ocr(new_page)
                ignore_rects = []
            else:
                continue
        tmp_path_prefix = os.path.join(sys.path[0], "tmp", "{}_page{}".format(filename, page_number))
        text_layer_path = os.path.join(sys.path[0], "tmp", "{}_page{}.pdf".format(filename, page_number))
        lines_to_draw = process_page(out_doc, new_page, extractor, tmp_path_prefix, confidence_threshold, ignore_rects)
        draw_ocr_text_page(new_page, text_layer_path, lines_to_draw)
    out_doc.save(out_path, deflate=True, garbage=3, use_objstms=1)

    # Verify that we can read the written document, and that it still has the same number of pages. Some corrupt input
    # documents might lead to an empty or to a corrupt output document, sometimes even without throwing an error. (See
    # LGD-283.) This check should detect such cases.
    doc = fitz.open(out_path)
    out_page_count = doc.page_count
    if in_page_count != out_page_count:
        raise ValueError(
            "Output document contains {} pages instead of {}".format(out_page_count, in_page_count)
        )


def main():
    if 'OCR_PROFILE' in os.environ:
        print(f"Loading env variables from .env and .env.{os.environ['OCR_PROFILE']}.")
        config = {
            **dotenv_values(".env"),
            **dotenv_values(f".env.{os.environ['OCR_PROFILE']}"),
        }
    else:
        print(f"Loading env variables from .env.")
        config = dotenv_values(".env")

    extractor = Textractor(profile_name=config["AWS_TEXTRACT_PROFILE"])
    confidence_threshold = float(config["CONFIDENCE_THRESHOLD"])
    aggressive_strategy = config["OCR_STRATEGY_AGGRESSIVE"] == "TRUE"
    print(f"Using confidence threshold {confidence_threshold} and aggressive strategy {aggressive_strategy}.")

    target = load_target(config)
    source = load_source(config, target)

    for asset_item in source.iterator():
        asset_item.load()
        out_path = target.local_path(asset_item)

        print()
        print(asset_item.filename)
        try:
            process(asset_item.filename, asset_item.local_path, out_path, extractor, confidence_threshold, aggressive_strategy)
        except (ValueError, mupdf.FzErrorArgument) as e:
            gs_preprocess_path = os.path.join(sys.path[0], "tmp", "gs_pre_" + asset_item.filename)
            print("Encountered {}: {}. Trying Ghostscript preprocessing.".format(e.__class__.__name__, e))
            subprocess.call([
                "ghostscript",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                "-dPDFSETTINGS=/default",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                "-sOutputFile={}".format(gs_preprocess_path),
                asset_item.local_path
            ])
            process(asset_item.filename, gs_preprocess_path, out_path, extractor, confidence_threshold, aggressive_strategy)
            os.remove(gs_preprocess_path)

        asset_item.cleanup()
        target.save(asset_item)
        target.cleanup(asset_item)


if __name__ == '__main__':
    main()
