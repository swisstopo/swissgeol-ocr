import os
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


class SharedSettings(BaseSettings):
    tmp_path: str

    confidence_threshold: float
    use_aggressive_strategy: bool = False


class ApiSettings(SharedSettings):
    aws_profile: str | None = None
    textract_aws_profile: str | None = None
    skip_processing: bool = False

    s3_input_endpoint: str
    s3_input_bucket: str
    s3_input_folder: str

    s3_output_endpoint: str
    s3_output_bucket: str
    s3_output_folder: str


class ScriptSettings(SharedSettings):
    cleanup_tmp_files: bool

    textract_aws_profile: str

    input_type: Literal['path', 's3']
    input_path: str | None = None
    input_aws_profile: str | None = None
    input_s3_bucket: str | None = None
    input_s3_prefix: str | None = None
    input_skip_existing: bool
    input_debug_page: int | None = None

    output_type: Literal['path', 's3']
    output_path: str | None = None
    output_aws_profile: str | None = None
    output_s3_bucket: str | None = None
    output_s3_prefix: str | None = None


print(f"Loading env variables from '.env'.")
load_dotenv()
if 'OCR_PROFILE' in os.environ:
    env_file = f".env.{os.environ['OCR_PROFILE']}"
    print(f"Loading env variables from '{env_file}'.")
    load_dotenv(env_file)


@lru_cache
def api_settings():
    return ApiSettings()


@lru_cache
def script_settings():
    return ScriptSettings()
