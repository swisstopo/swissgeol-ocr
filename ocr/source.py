import os
import shutil
from collections.abc import Iterator
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path


class AssetItem:
    tmp_dir: Path
    filename: str

    @abstractmethod
    def load(self):
        pass

    @property
    def tmp_path(self):
        return self.tmp_dir / self.filename

    @property
    def result_tmp_path(self) -> Path:
        return self.tmp_dir / ("new_" + self.filename)


class FileAssetItem(AssetItem):
    def __init__(self, in_path: Path, tmp_dir: Path):
        self.in_path = in_path
        self.filename = os.path.basename(in_path)
        self.tmp_dir = tmp_dir / self.filename  # separate tmp dir per file

    def load(self):
        shutil.copy(self.in_path, self.tmp_path)


class S3AssetItem(AssetItem):
    def __init__(self, s3_bucket: any, s3_key: str, allow_override: bool, tmp_dir: Path):
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        self.filename = S3AssetItem.key_to_filename(self.s3_key)
        self.allow_override = allow_override
        self.tmp_dir = tmp_dir / self.filename  # separate tmp dir per file

    def load(self):
        if self.allow_override or not os.path.exists(self.tmp_path):
            self.s3_bucket.download_file(self.s3_key, self.tmp_path)

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
    skip_filenames: set[str]
    tmp_dir: Path

    def iterator(self) -> Iterator[AssetItem]:
        if self.in_path.is_dir():
            return (
                FileAssetItem(
                    in_path=path,
                    tmp_dir=self.tmp_dir
                )
                for path in sorted(self.in_path.glob("*"))
                if os.path.basename(path).endswith(".pdf") and os.path.basename(path) not in self.skip_filenames
            )
        else:
            return iter([FileAssetItem(
                in_path=self.in_path,
                tmp_dir=self.tmp_dir
            )])


@dataclass
class S3AssetSource(AssetSource):
    s3_bucket: any
    s3_prefix: str
    allow_override: bool
    skip_filenames: set[str]
    tmp_dir: Path

    def iterator(self) -> Iterator[AssetItem]:
        objs = list(self.s3_bucket.objects.filter(Prefix=self.s3_prefix))

        return (
            S3AssetItem(
                s3_bucket=self.s3_bucket,
                s3_key=obj.key,
                allow_override=self.allow_override,
                tmp_dir=self.tmp_dir
            )
            for obj in objs
            if obj.size
            if obj.key.lower().endswith(".pdf")
            if S3AssetItem.key_to_filename(obj.key) not in self.skip_filenames
        )
