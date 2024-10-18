import os
from abc import abstractmethod
from dataclasses import dataclass
from typing import Callable
from pathlib import Path

from ocr.source import AssetItem, S3AssetItem


class AssetTarget:
    @abstractmethod
    def save(self, item: AssetItem):
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

    def save(self, item: AssetItem):
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
    output_path_fn: Callable[[str], Path]

    def save(self, item: AssetItem):
        self.s3_bucket.upload_file(self.local_path(item), self.s3_prefix + item.filename)

    def local_path(self, item: AssetItem) -> Path:
        return self.output_path_fn(item.filename)

    def existing_filenames(self) -> set[str]:
        return {
            S3AssetItem.key_to_filename(obj.key)
            for obj in self.s3_bucket.objects.filter(Prefix=self.s3_prefix)
        }
