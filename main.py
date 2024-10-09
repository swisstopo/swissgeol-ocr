import os
import shutil
import sys
from pathlib import Path

import boto3
from dotenv import dotenv_values
from textractor import Textractor

import ocr
from ocr.source import S3AssetSource, FileAssetSource
from ocr.target import S3AssetTarget, FileAssetTarget, AssetTarget


def load_target(config):
    if config["OCR_OUTPUT_TYPE"] == "S3":
        s3_session = boto3.Session(profile_name=config["OCR_OUTPUT_AWS_PROFILE"])
        s3 = s3_session.resource('s3')
        return S3AssetTarget(
            s3_bucket=s3.Bucket(config["OCR_OUTPUT_S3_BUCKET"]),
            s3_prefix=config["OCR_OUTPUT_S3_PREFIX"],
            output_path_fn=lambda filename: Path(sys.path[0], "tmp", "new_" + filename),
        )
    elif config["OCR_OUTPUT_TYPE"] == "path":
        return FileAssetTarget(
            out_path=Path(config["OCR_OUTPUT_PATH"])
        )
    else:
        print("No OCR_OUTPUT_TYPE specified.")
        sys.exit(1)


def load_source(config, target: AssetTarget):
    if config["OCR_INPUT_IGNORE_EXISTING"] == "TRUE":
        ignore_filenames = target.existing_filenames()
        print("Found {} existing objects in output path.".format(len(ignore_filenames)))
    else:
        ignore_filenames = []

    if config["OCR_INPUT_TYPE"] == "S3":
        s3_session = boto3.Session(profile_name=config["OCR_INPUT_AWS_PROFILE"])
        s3 = s3_session.resource('s3')

        return S3AssetSource(
            s3_bucket=s3.Bucket(config["OCR_INPUT_S3_BUCKET"]),
            s3_prefix=config["OCR_INPUT_S3_PREFIX"],
            allow_override=False,
            input_path_fn=lambda filename: Path(sys.path[0], "tmp", filename),
            ignore_filenames=ignore_filenames
        )
    elif config["OCR_INPUT_TYPE"] == "path":
        return FileAssetSource(
            in_path=Path(config["OCR_INPUT_PATH"]),
            ignore_filenames=ignore_filenames
        )
    else:
        print("No OCR_INPUT_TYPE specified.")
        sys.exit(1)


def main():
    if 'OCR_PROFILE' in os.environ:
        print(f"Loading env variables from .env and .env.{os.environ['OCR_PROFILE']}.")
        config = {
            **dotenv_values(".env"),
            **dotenv_values(f".env.{os.environ['OCR_PROFILE']}"),
        }
    else:
        print(f"Loading env variables from .env.")
        config = dotenv_values(".env")

    extractor = Textractor(profile_name=config["AWS_TEXTRACT_PROFILE"])
    confidence_threshold = float(config["CONFIDENCE_THRESHOLD"])
    aggressive_strategy = config["OCR_STRATEGY_AGGRESSIVE"] == "TRUE"
    print(f"Using confidence threshold {confidence_threshold} and aggressive strategy {aggressive_strategy}.")

    target = load_target(config)
    source = load_source(config, target)

    for asset_item in source.iterator():
        asset_item.load()
        out_path = target.local_path(asset_item)
        tmp_dir = os.path.join("tmp", asset_item.filename)

        print()
        print(asset_item.filename)
        ocr.process(
            str(asset_item.local_path),
            str(out_path),
            tmp_dir,
            extractor.textract_client,
            confidence_threshold,
            aggressive_strategy,
        )

        target.save(asset_item)
        shutil.rmtree(tmp_dir)


if __name__ == '__main__':
    main()
