import os
from collections.abc import Iterator
from abc import abstractmethod
from dataclasses import dataclass
from typing import Callable
from pathlib import Path


class AssetItem:
    local_path: Path
    filename: str

    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def cleanup(self):
        pass


@dataclass
class FileAssetItem(AssetItem):
    local_path: Path
    filename: str

    def load(self):
        pass

    def cleanup(self):
        pass


@dataclass
class S3AssetItem(AssetItem):
    s3_bucket: any
    s3_key: str
    local_path: Path
    allow_override: bool
    do_cleanup: bool

    def __post_init__(self):
        self.filename = S3AssetItem.key_to_filename(self.s3_key)

    def load(self):
        if self.allow_override or not os.path.exists(self.local_path):
            self.s3_bucket.download_file(self.s3_key, self.local_path)

    def cleanup(self):
        if self.do_cleanup:
            os.remove(self.local_path)

    @staticmethod
    def key_to_filename(key):
        return key.split("/")[-1]


class AssetSource:
    @abstractmethod
    def iterator(self) -> Iterator[AssetItem]:
        pass


@dataclass
class FileAssetSource(AssetSource):
    in_path: Path
    ignore_filenames: set[str]

    def iterator(self) -> Iterator[AssetItem]:
        if self.in_path.is_dir():
            return (
                FileAssetItem(local_path=path, filename=os.path.basename(path))
                for path in sorted(self.in_path.glob("*"))
                if os.path.basename(path).endswith(".pdf") and os.path.basename(path) not in self.ignore_filenames
            )
        else:
            return [
                FileAssetItem(local_path=self.in_path, filename=os.path.basename(self.in_path))
            ]


@dataclass
class S3AssetSource(AssetSource):
    s3_bucket: any
    s3_prefix: str
    input_path_fn: Callable[[str], Path]
    allow_override: bool
    do_cleanup: bool
    ignore_filenames: set[str]

    def iterator(self) -> Iterator[AssetItem]:
        objs = list(self.s3_bucket.objects.filter(Prefix=self.s3_prefix))

        return (
            S3AssetItem(
                s3_bucket=self.s3_bucket,
                s3_key=obj.key,
                local_path=self.input_path_fn(S3AssetItem.key_to_filename(obj.key)),
                allow_override=self.allow_override,
                do_cleanup=self.do_cleanup
            )
            for obj in objs
            if obj.size
            if obj.key.lower().endswith(".pdf")
            if S3AssetItem.key_to_filename(obj.key) not in self.ignore_filenames
        )
