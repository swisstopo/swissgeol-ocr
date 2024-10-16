from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError
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

    def exists_file(self, bucket_name: str, key: str) -> bool:
        try:
            self.s3.Object(bucket_name, key).load()
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                raise e


def connect(settings: ApiSettings) -> Client:
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
