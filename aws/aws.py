from dataclasses import dataclass
from typing import Protocol

import boto3
from botocore.exceptions import ClientError
from mypy_boto3_s3 import S3ServiceResource
from mypy_boto3_s3.service_resource import Bucket
from mypy_boto3_textract import TextractClient as Textractor

from ocr import ProcessResult
from utils.settings import ApiSettings

type S3Bucket = any
type S3ObjectMetadata = dict[str, str]


class SupportsStr(Protocol):
    def __str__(self) -> str: ...


# note: AWS stores metadata keys in lower case per default
METADATA_PAGE_COUNT_KEY = "pagecount"


@dataclass
class Client:
    s3_input: S3ServiceResource
    s3_output: S3ServiceResource
    textract: Textractor

    def exists_input_file(self, bucket_name: str, key: str) -> bool:
        try:
            self.s3_input.Object(bucket_name, key).load()
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

    if is_set(settings.textract_aws_profile):
        textract_session = open_session_by_profile(settings.textract_aws_profile)
    else:
        textract_session = session

    return Client(
        s3_input=session.resource('s3', endpoint_url=settings.s3_input_endpoint),
        s3_output=session.resource('s3', endpoint_url=settings.s3_output_endpoint),
        textract=textract_session.client('textract')
    )


def is_set(value: str | None) -> bool:
    return value is not None and len(value) > 0


def open_session_by_profile(profile: str) -> boto3.Session:
    return boto3.Session(profile_name=profile)


def open_session_by_service_role() -> boto3.Session:
    return boto3.Session()


def load_file(bucket: Bucket, key: str, local_path: str):
    bucket.download_file(key, local_path)


def store_file(bucket: Bucket, key: str, local_path: str, process_result: ProcessResult):
    bucket.upload_file(local_path, key, ExtraArgs={
        'ContentType': 'application/pdf',
        'Metadata': {
            **_parse_metadata(METADATA_PAGE_COUNT_KEY, process_result.number_of_pages)
        }
    })


def _parse_metadata(key: str, value: SupportsStr | None) -> S3ObjectMetadata:
    return {key: str(value)} if value else {}
