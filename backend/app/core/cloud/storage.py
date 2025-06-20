import os

# import logging
import functools as ft
from pathlib import Path
from dataclasses import dataclass, asdict
from urllib.parse import ParseResult, urlparse, urlunparse

import boto3
from fastapi import UploadFile
from botocore.exceptions import ClientError
from botocore.response import StreamingBody

from app.api.deps import CurrentUser
from app.core.config import settings


class CloudStorageError(Exception):
    pass


class AmazonCloudStorageClient:
    @ft.cached_property
    def client(self):
        kwargs = {}
        cred_params = (
            ("aws_access_key_id", "AWS_ACCESS_KEY_ID"),
            ("aws_secret_access_key", "AWS_SECRET_ACCESS_KEY"),
            ("region_name", "AWS_DEFAULT_REGION"),
        )

        for i, j in cred_params:
            kwargs[i] = os.environ.get(j, getattr(settings, j))

        return boto3.client("s3", **kwargs)

    def create(self):
        try:
            # does the bucket exist...
            self.client.head_bucket(Bucket=settings.AWS_S3_BUCKET)
        except ValueError as err:
            raise CloudStorageError(err) from err
        except ClientError as err:
            response = int(err.response["Error"]["Code"])
            if response != 404:
                raise CloudStorageError(err) from err
            # ... if not create it
            self.client.create_bucket(
                Bucket=settings.AWS_S3_BUCKET,
                CreateBucketConfiguration={
                    "LocationConstraint": settings.AWS_DEFAULT_REGION,
                },
            )


@dataclass(frozen=True)
class SimpleStorageName:
    Key: str
    Bucket: str = settings.AWS_S3_BUCKET

    def __str__(self):
        return urlunparse(self.to_url())

    def to_url(self):
        kwargs = {
            "scheme": "s3",
            "netloc": self.Bucket,
            "path": self.Key,
        }
        for k in ParseResult._fields:
            kwargs.setdefault(k)

        return ParseResult(**kwargs)

    @classmethod
    def from_url(cls, url: str):
        url = urlparse(url)
        path = Path(url.path)
        if path.is_absolute():
            path = path.relative_to(path.root)

        return cls(Bucket=url.netloc, Key=str(path))


class CloudStorage:
    def __init__(self, user: CurrentUser):
        self.user = user

    def put(self, source: UploadFile, basename: str):
        raise NotImplementedError()

    def stream(self, url: str) -> StreamingBody:
        raise NotImplementedError()


class AmazonCloudStorage(CloudStorage):
    def __init__(self, user: CurrentUser):
        super().__init__(user)
        self.aws = AmazonCloudStorageClient()

    def put(self, source: UploadFile, basename: Path) -> SimpleStorageName:
        key = Path(str(self.user.id), basename)
        destination = SimpleStorageName(str(key))

        kwargs = asdict(destination)
        try:
            self.aws.client.upload_fileobj(
                source.file,
                ExtraArgs={
                    # 'Metadata': self.user.model_dump(),
                    "ContentType": source.content_type,
                },
                **kwargs,
            )
        except ClientError as err:
            raise CloudStorageError(f'AWS Error: "{err}"') from err

        return destination

    def stream(self, url: str) -> StreamingBody:
        name = SimpleStorageName.from_url(url)
        kwargs = asdict(name)
        try:
            return self.aws.client.get_object(**kwargs).get("Body")
        except ClientError as err:
            raise CloudStorageError(f'AWS Error: "{err}" ({url})') from err

    def delete(self, url: str) -> None:
        name = SimpleStorageName.from_url(url)
        kwargs = asdict(name)
        try:
            self.aws.client.delete_object(**kwargs)
        except ClientError as err:
            raise CloudStorageError(f'AWS Error: "{err}" ({url})') from err
