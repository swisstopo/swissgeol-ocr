from abc import abstractmethod
from dataclasses import dataclass

import boto3
from mypy_boto3_textract import TextractClient as Textractor
from mypy_boto3_s3 import S3ServiceResource
from mypy_boto3_s3.service_resource import Bucket

from utils.settings import Settings

type S3Bucket = any


@dataclass
class Client:
    s3: S3ServiceResource
    textract: Textractor

    def bucket(self, name: str) -> Bucket:
        return self.s3.Bucket(name)


def connect(settings: Settings) -> Client:
    has_profile = is_set(settings.aws_profile)
    if has_profile:
        session = open_session_by_profile(settings.aws_profile)
    else:
        session = open_session_by_service_role()

    return Client(
        s3=session.resource('s3'),
        textract=session.client('textract')
    )


def is_set(value: str | None) -> bool:
    return value is not None and len(value) > 0


def open_session_by_profile(profile: str) -> boto3.Session:
    return boto3.Session(profile_name=profile)


def open_session_by_service_role() -> boto3.Session:
    return boto3.Session()


def load_file(bucket: Bucket, key: str, local_path: str):
    bucket.download_file(key, local_path)


def store_file(bucket: Bucket, key: str, local_path: str):
    bucket.upload_file(local_path, key)
