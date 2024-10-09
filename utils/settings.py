import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    tmp_path: str

    aws_profile: str | None = None

    s3_input_bucket: str
    s3_input_folder: str

    s3_output_bucket: str
    s3_output_folder: str

    confidence_threshold: float
    use_aggressive_strategy: bool = False


print(f"Loading env variables from '.env'.")
load_dotenv()

@lru_cache
def get_settings():
    return Settings()