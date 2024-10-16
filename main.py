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
            output_path_fn=lambda filename: Path(sys.path[0], "tmp", "new_" + filename),
        )
    elif settings.output_type == 'path':
        return FileAssetTarget(
            out_path=Path(settings.output_path)
        )
    else:
        print("No output type specified.")
        sys.exit(1)


def load_source(settings: ScriptSettings, target: AssetTarget):
    if settings.input_type == 's3':
        ignore_filenames = target.existing_filenames()
        print("Found {} existing objects in output path.".format(len(ignore_filenames)))
    else:
        ignore_filenames = []

    if settings.input_type == "s3":
        s3_session = boto3.Session(profile_name=settings.input_aws_profile)
        s3 = s3_session.resource('s3')

        return S3AssetSource(
            s3_bucket=s3.Bucket(settings.input_s3_bucket),
            s3_prefix=settings.input_s3_prefix,
            allow_override=False,
            input_path_fn=lambda filename: Path(sys.path[0], "tmp", filename),
            ignore_filenames=ignore_filenames
        )
    elif settings.input_type == "path":
        return FileAssetSource(
            in_path=Path(settings.input_path),
            ignore_filenames=ignore_filenames
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
        asset_item.load()
        out_path = target.local_path(asset_item)
        tmp_dir = os.path.join(settings.tmp_path, asset_item.filename)

        print()
        print(asset_item.filename)
        ocr.process(
            str(asset_item.local_path),
            str(out_path),
            tmp_dir,
            extractor.textract_client,
            settings.confidence_threshold,
            settings.use_aggressive_strategy,
        )

        target.save(asset_item)

        if settings.cleanup_tmp_files:
            shutil.rmtree(tmp_dir)


if __name__ == '__main__':
    main()
