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
    has_role = is_set(settings.ocr_role)
    has_profile = is_set(settings.ocr_profile)
    if has_role and has_profile:
        raise \
            'Please specify only one of OCR_ROLE and OCR_PROFILE.' \
            'This determines how you want to authenticate with AWS.'
    if not has_role and not has_profile:
        raise \
            'Missing either one of OCR_ROLE or OCR_PROFILE.' \
            'This determines how you want to authenticate with AWS.'


    if has_role:
        session = open_session_by_service_role(settings.ocr_role)
    else:
        session = open_session_by_profile(settings.ocr_profile)

    return Client(
        s3=session.resource('s3'),
        textract=session.client('textract')
    )


def is_set(value: str | None) -> bool:
    return value is not None and len(value) > 0

def open_session_by_profile(profile: str) -> boto3.Session:
    return boto3.Session(profile_name=profile)

def open_session_by_service_role(role: str) -> boto3.Session:
    sts_client = boto3.client('sts')
    response = sts_client.assume_role(
        RoleArn=role,
        RoleSessionName='swissgeol-ocr',
    )
    credentials = response['Credentials']
    return boto3.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )

def load_file(bucket: Bucket, key: str, local_path: str):
    bucket.download_file(key, local_path)

def store_file(bucket: Bucket, key: str, local_path: str):
    bucket.upload_file(local_path, key)
