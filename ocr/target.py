import os
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path

from aws import aws
from ocr import ProcessResult
from ocr.source import AssetItem, S3AssetItem


class AssetTarget:
    @abstractmethod
    def save(self, item: AssetItem, process_result: ProcessResult):
        pass

    @abstractmethod
    def local_path(self, item: AssetItem) -> Path:
        pass

    @abstractmethod
    def existing_filenames(self) -> set[str]:
        pass


@dataclass
class FileAssetTarget(AssetTarget):
    out_path: Path

    def save(self, item: AssetItem, process_result: ProcessResult):
        pass

    def local_path(self, item: AssetItem) -> Path:
        return Path(self.out_path, item.filename)

    def existing_filenames(self) -> set[str]:
        return {
            os.path.basename(path)
            for path in sorted(self.out_path.glob("*"))
        }


@dataclass
class S3AssetTarget(AssetTarget):
    s3_bucket: any
    s3_prefix: str
    tmp_dir: Path

    def save(self, item: AssetItem, process_result: ProcessResult):
        aws.store_file(
            bucket=self.s3_bucket,
            key=self.s3_prefix + item.filename,
            local_path=str(self.local_path(item)),
            process_result=process_result
        )

    def local_path(self, item: AssetItem) -> Path:
        return item.tmp_path / ("new_" + item.filename)

    def existing_filenames(self) -> set[str]:
        return {
            S3AssetItem.key_to_filename(obj.key)
            for obj in self.s3_bucket.objects.filter(Prefix=self.s3_prefix)
        }
