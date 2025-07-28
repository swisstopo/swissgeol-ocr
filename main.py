import os
import shutil
import sys
from pathlib import Path

import boto3
from textractor import Textractor

import ocr
from ocr.source import S3AssetSource, FileAssetSource
from ocr.target import S3AssetTarget, FileAssetTarget, AssetTarget
from utils.settings import script_settings, ScriptSettings


def load_target(settings: ScriptSettings):
    if settings.output_type == 's3':
        s3_session = boto3.Session(profile_name=settings.output_aws_profile)
        s3 = s3_session.resource('s3')
        return S3AssetTarget(
            s3_bucket=s3.Bucket(settings.output_s3_bucket),
            s3_prefix=settings.output_s3_prefix,
            tmp_dir=Path(settings.tmp_path)
        )
    elif settings.output_type == 'path':
        return FileAssetTarget(
            out_path=Path(settings.output_path)
        )
    else:
        print("No output type specified.")
        sys.exit(1)


def load_source(settings: ScriptSettings, target: AssetTarget):
    if settings.input_skip_existing:
        skip_filenames = target.existing_filenames()
        print("Found {} existing objects in output path.".format(len(skip_filenames)))
    else:
        skip_filenames = []

    if settings.input_type == "s3":
        s3_session = boto3.Session(profile_name=settings.input_aws_profile)
        s3 = s3_session.resource('s3')

        return S3AssetSource(
            s3_bucket=s3.Bucket(settings.input_s3_bucket),
            s3_prefix=settings.input_s3_prefix,
            allow_override=False,
            skip_filenames=skip_filenames,
            tmp_dir=Path(settings.tmp_path)
        )
    elif settings.input_type == "path":
        return FileAssetSource(
            in_path=Path(settings.input_path),
            skip_filenames=skip_filenames,
            tmp_dir=Path(settings.tmp_path)
        )
    else:
        print("No input type specified.")
        sys.exit(1)


def main():
    settings = script_settings()
    extractor = Textractor(profile_name=settings.textract_aws_profile)

    target = load_target(settings)
    source = load_source(settings, target)

    for asset_item in source.iterator():
        os.makedirs(asset_item.tmp_path, exist_ok=True)
        asset_item.load()
        out_path = target.local_path(asset_item)

        print()
        print(asset_item.filename)
        process_result = ocr.Processor(
            asset_item.local_path,
            settings.input_debug_page,
            out_path,
            asset_item.tmp_path,
            extractor.textract_client,
            settings.confidence_threshold,
            settings.use_aggressive_strategy,
        ).process()

        target.save(asset_item, process_result)

        if settings.cleanup_tmp_files:
            shutil.rmtree(asset_item.tmp_path)


if __name__ == '__main__':
    main()
