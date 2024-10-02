import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    tmp_path: str

    ocr_profile: str | None = None
    ocr_role: str | None = None

    ocr_input_s3_bucket: str
    ocr_input_s3_prefix: str

    ocr_output_s3_bucket: str
    ocr_output_s3_prefix: str

    confidence_threshold: float
    ocr_strategy_aggressive: bool = False


print(f"Loading env variables from '.env'.")
load_dotenv()

@lru_cache
def get_settings():
    return Settings()