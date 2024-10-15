from dataclasses import dataclass

import boto3
from mypy_boto3_s3 import S3ServiceResource
from mypy_boto3_s3.service_resource import Bucket
from mypy_boto3_textract import TextractClient as Textractor

from utils.settings import ApiSettings

type S3Bucket = any


@dataclass
class Client:
    s3: S3ServiceResource
    textract: Textractor

    def bucket(self, name: str) -> Bucket:
        return self.s3.Bucket(name)


def connect(settings: ApiSettings) -> Client:
    has_profile = is_set(settings.aws_profile)
    has_access_key = is_set(settings.aws_access_key)
    has_secret_access_key = is_set(settings.aws_secret_access_key)

    if (has_access_key and not has_secret_access_key) or (not has_access_key and has_secret_access_key):
        print("Either both or none of AWS_ACCESS_KEY and AWS_SECRET_ACCESS_KEY must be set.")
        exit(1)

    if has_profile and has_access_key:
        print("Can't use both AWS_PROFILE and secret keys.")
        exit(1)

    if has_profile:
        session = open_session_by_profile(settings.aws_profile)
    elif has_access_key:
        session = open_session_by_access_keys(
            settings.aws_access_key,
            settings.aws_secret_access_key,
            settings.aws_region,
        )
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


def open_session_by_access_keys(access_key: str, secret_access_key: str, region: str) -> boto3.Session:
    return boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_access_key,
        region_name=region,
    )


def open_session_by_service_role() -> boto3.Session:
    return boto3.Session()


def load_file(bucket: Bucket, key: str, local_path: str):
    bucket.download_file(key, local_path)


def store_file(bucket: Bucket, key: str, local_path: str):
    bucket.upload_file(local_path, key)
