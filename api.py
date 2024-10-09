import os
import shutil
import subprocess
import uuid
from typing import Annotated

from fastapi import FastAPI, Depends, status, HTTPException, BackgroundTasks, Response
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

import ocr
from aws import aws
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
        aws_client.bucket(settings.s3_input_bucket),
        f'{settings.s3_input_folder}{payload.file}',
        input_path,
    )

    ocr.process(
        input_path,
        output_path,
        tmp_dir,
        aws_client.textract,
        settings.confidence_threshold,
        settings.use_aggressive_strategy,
    )

    aws.store_file(
        aws_client.bucket(settings.s3_output_bucket),
        f'{settings.s3_output_folder}{payload.file}',
        output_path,
    )

    shutil.rmtree(tmp_dir)
    return ()
