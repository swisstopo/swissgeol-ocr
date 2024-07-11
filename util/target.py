import os
from abc import abstractmethod
from dataclasses import dataclass
from typing import Callable
from pathlib import Path

from util.source import AssetItem, S3AssetItem


class AssetTarget:
    @abstractmethod
    def save(self, item: AssetItem):
        pass

    @abstractmethod
    def local_path(self, item: AssetItem) -> Path:
        pass

    @abstractmethod
    def cleanup(self, item: AssetItem):
        pass


@dataclass
class FileAssetTarget(AssetTarget):
    out_path: Path

    def save(self, item: AssetItem):
        pass

    def local_path(self, item: AssetItem) -> Path:
        return Path(self.out_path, item.filename)

    def cleanup(self, item: AssetItem):
        pass


@dataclass
class S3AssetTarget(AssetTarget):
    s3_bucket: any
    s3_prefix: str
    output_path_fn: Callable[[str], Path]
    do_cleanup: bool

    def save(self, item: AssetItem):
        self.s3_bucket.upload_file(self.local_path(item), self.s3_prefix + item.filename)

    def local_path(self, item: AssetItem) -> Path:
        return self.output_path_fn(item.filename)

    def cleanup(self, item: AssetItem):
        if self.do_cleanup:
            os.remove(self.local_path(item))

    def existing_filenames(self):
        existing_filenames = {
            S3AssetItem.key_to_filename(obj.key)
            for obj in self.s3_bucket.objects.filter(Prefix=self.s3_prefix)
        }
        print("Found {} existing objects in output path.".format(len(existing_filenames)))
        return existing_filenames

