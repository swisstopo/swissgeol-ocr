import logging
import os
import shutil
import uuid
from typing import Annotated

from fastapi import FastAPI, Depends, status, HTTPException, BackgroundTasks, Response
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse
from pathlib import Path

import ocr
from aws import aws
from utils import task
from utils.settings import ApiSettings, api_settings

app = FastAPI()

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)


class StartPayload(BaseModel):
    file: str = Field(min_length=1)


if api_settings().skip_processing:
    logging.warning("SKIP_PROCESSING is active, files will always be marked as completed without being proceed")


@app.post("/")
def start(
        payload: StartPayload,
        settings: Annotated[ApiSettings, Depends(api_settings)],
        background_tasks: BackgroundTasks,
):
    if not payload.file.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "input must be a PDF file"}
        )

    aws_client = aws.connect(settings)
    has_file = aws_client.exists_file(
        settings.s3_input_bucket,
        f'{settings.s3_input_folder}{payload.file}',
    )
    if not has_file:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "file does not exist"}
        )

    task.start(payload.file, background_tasks, lambda: process(payload, aws_client, settings))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class CollectPayload(BaseModel):
    file: str = Field(min_length=1)


@app.post("/collect")
def collect(
        payload: CollectPayload,
):
    result = task.collect_result(payload.file)
    if result is None and not task.has_task(payload.file):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "OCR is not running for this file"}
        )

    has_finished = result is not None
    if not has_finished:
        logging.info(f"Processing of '{payload.file}' has not yet finished.")
        return JSONResponse(status_code=status.HTTP_200_OK, content={
            "has_finished": False,
            "data": None,
        })

    if result.ok:
        logging.info(f"Processing of '{payload.file}' has been successful.")
        return JSONResponse(status_code=status.HTTP_200_OK, content={
            "has_finished": True,
            "data": result.value,
        })

    logging.info(f"Processing of '{payload.file}' has failed.")
    return JSONResponse(status_code=status.HTTP_200_OK, content={
        "has_finished": True,
        "error": "Internal Server Error",
    })


def process(
        payload: StartPayload,
        aws_client: aws.Client,
        settings: Annotated[ApiSettings, Depends(api_settings)],
):
    if settings.skip_processing:
        # Sleep between 30 seconds to 2 minutes to simulate processing time.
        # sleep(randint(30, 120))
        return

    task_id = f"{uuid.uuid4()}"
    tmp_dir = Path(settings.tmp_path) / task_id
    os.makedirs(tmp_dir, exist_ok=True)

    input_path = tmp_dir / "input.pdf"
    output_path = tmp_dir / "output.pdf"

    aws.load_file(
        aws_client.bucket(settings.s3_input_bucket),
        f'{settings.s3_input_folder}{payload.file}',
        str(input_path),
    )

    ocr.Processor(
        input_path=input_path,
        debug_page=None,
        output_path=output_path,
        tmp_dir=tmp_dir,
        textractor=aws_client.textract,
        confidence_threshold=settings.confidence_threshold,
        use_aggressive_strategy=settings.use_aggressive_strategy,
    ).process()

    aws.store_file(
        aws_client.bucket(settings.s3_output_bucket),
        f'{settings.s3_output_folder}{payload.file}',
        str(output_path),
    )

    shutil.rmtree(tmp_dir)
    return ()
