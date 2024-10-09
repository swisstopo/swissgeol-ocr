import os
import shutil
import subprocess
import uuid
from typing import Annotated

import fitz
from fastapi import FastAPI, Depends, status, HTTPException, BackgroundTasks, Response
from mypy_boto3_textract import TextractClient as Textractor
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from aws import aws
from ocr.crop import crop_images
from ocr.resize import resize_page
from ocr.util import process_page, clean_old_ocr, new_ocr_needed, draw_ocr_text_page, clean_old_ocr_aggressive
from utils import task
from utils.settings import Settings, get_settings

app = FastAPI()


class StartPayload(BaseModel):
    file: str = Field(min_length=1)


@app.post("/")
def start(
        payload: StartPayload,
        settings: Annotated[Settings, Depends(get_settings)],
        background_tasks: BackgroundTasks,
):
    if not payload.file.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid request", "message": "input must be a PDF file"}
        )

    task.start(payload.file, background_tasks, lambda: process(payload, settings))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class CollectPayload(BaseModel):
    file: str = Field(min_length=1)


@app.post("/collect")
def collect(
        payload: CollectPayload,
):
    result = task.collect_result(payload.file)
    if result is None and not task.has_task(payload.file):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": "OCR is not running for this file"},
        )
    return JSONResponse(status_code=status.HTTP_200_OK, content={
        "has_finished": result is not None,
        "data": result,
    })


def process(
        payload: StartPayload,
        settings: Annotated[Settings, Depends(get_settings)],
):
    task_id = f"{uuid.uuid4()}"
    tmp_dir = os.path.join(settings.tmp_path, task_id)
    os.makedirs(tmp_dir, exist_ok=True)

    input_path = os.path.join(tmp_dir, "input.pdf")
    output_path = os.path.join(tmp_dir, "output.pdf")

    aws_client = aws.connect(settings)
    aws.load_file(
        aws_client.bucket(settings.ocr_input_s3_bucket),
        f'{settings.ocr_input_s3_prefix}{payload.file}',
        input_path,
    )

    try:
        process_text(
            input_path,
            output_path,
            tmp_dir,
            aws_client.textract,
            settings.confidence_threshold,
            settings.ocr_strategy_aggressive
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
        process_text(
            gs_preprocess_path,
            output_path,
            tmp_dir,
            aws_client.textract,
            settings.confidence_threshold,
            settings.ocr_strategy_aggressive,
        )

    aws.store_file(
        aws_client.bucket(settings.ocr_output_s3_bucket),
        f'{settings.ocr_output_s3_prefix}{payload.file}',
        output_path,
    )

    shutil.rmtree(tmp_dir)
    return ()


def process_text(
        in_path: str,
        out_path: str,
        tmp_dir: str,
        textractor: Textractor,
        confidence_threshold: float,
        aggressive_strategy: bool,
):
    in_doc = fitz.open(in_path)
    out_doc = fitz.open(in_path)

    in_page_count = in_doc.page_count
    print(f"{in_page_count} pages")

    for page_index, new_page in enumerate(in_doc):
        page_number = page_index + 1
        print(f"Page {page_number}")

        new_page = resize_page(in_doc, out_doc, page_index)
        crop_images(new_page, out_doc)
        if aggressive_strategy:
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
    out_doc.save(out_path, garbage=3, deflate=True)

    # Verify that we can read the written document, and that it still has the same number of pages. Some corrupt input
    # documents might lead to an empty or to a corrupt output document, sometimes even without throwing an error. (See
    # LGD-283.) This check should detect such cases.
    doc = fitz.open(out_path)
    out_page_count = doc.page_count
    if in_page_count != out_page_count:
        raise ValueError(
            "Output document contains {} pages instead of {}".format(out_page_count, in_page_count)
        )
