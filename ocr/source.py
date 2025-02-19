import os
from collections.abc import Iterator
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path


class AssetItem:
    local_path: Path
    tmp_path: Path
    filename: str

    @abstractmethod
    def load(self):
        pass


@dataclass
class FileAssetItem(AssetItem):
    local_path: Path
    filename: str
    tmp_path: Path

    def load(self):
        pass

@dataclass
class S3AssetItem(AssetItem):
    s3_bucket: any
    s3_key: str
    allow_override: bool
    tmp_path: Path

    def __post_init__(self):
        self.filename = S3AssetItem.key_to_filename(self.s3_key)
        self.local_path = self.tmp_path / self.filename

    def load(self):
        if self.allow_override or not os.path.exists(self.local_path):
            self.s3_bucket.download_file(self.s3_key, self.local_path)

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
                    local_path=path,
                    filename=os.path.basename(path),
                    tmp_path=self.tmp_dir / os.path.basename(path)
                )
                for path in sorted(self.in_path.glob("*"))
                if os.path.basename(path).endswith(".pdf") and os.path.basename(path) not in self.skip_filenames
            )
        else:
            return iter([FileAssetItem(
                local_path=self.in_path,
                filename=os.path.basename(self.in_path),
                tmp_path=self.tmp_dir / os.path.basename(self.in_path)
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
                tmp_path=self.tmp_dir / os.path.basename(S3AssetItem.key_to_filename(obj.key))
            )
            for obj in objs
            if obj.size
            if obj.key.lower().endswith(".pdf")
            if S3AssetItem.key_to_filename(obj.key) not in self.skip_filenames
        )
