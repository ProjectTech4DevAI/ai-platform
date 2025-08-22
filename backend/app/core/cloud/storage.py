import os
import logging
import functools as ft
from pathlib import Path
from dataclasses import dataclass, asdict
from urllib.parse import ParseResult, urlparse, urlunparse

import boto3
from fastapi import UploadFile
from botocore.exceptions import ClientError
from botocore.response import StreamingBody

from app.models import UserProjectOrg
from app.core.config import settings
from app.utils import mask_string

logger = logging.getLogger(__name__)


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

        client = boto3.client("s3", **kwargs)
        return client

    def create(self):
        try:
            self.client.head_bucket(Bucket=settings.AWS_S3_BUCKET)
        except ValueError as err:
            logger.error(
                f"[AmazonCloudStorageClient.create] Invalid bucket configuration | "
                f"{{'bucket': '{mask_string(settings.AWS_S3_BUCKET)}', 'error': '{str(err)}'}}",
                exc_info=True,
            )
            raise CloudStorageError(err) from err
        except ClientError as err:
            response = int(err.response["Error"]["Code"])
            if response != 404:
                logger.error(
                    f"[AmazonCloudStorageClient.create] Unexpected AWS error | "
                    f"{{'bucket': '{mask_string(settings.AWS_S3_BUCKET)}', 'error': '{str(err)}', 'code': {response}}}",
                    exc_info=True,
                )
                raise CloudStorageError(err) from err
            logger.warning(
                f"[AmazonCloudStorageClient.create] Bucket not found, creating | "
                f"{{'bucket': '{mask_string(settings.AWS_S3_BUCKET)}'}}"
            )
            try:
                self.client.create_bucket(
                    Bucket=settings.AWS_S3_BUCKET,
                    CreateBucketConfiguration={
                        "LocationConstraint": settings.AWS_DEFAULT_REGION,
                    },
                )
                logger.info(
                    f"[AmazonCloudStorageClient.create] Bucket created successfully | "
                    f"{{'bucket': '{mask_string(settings.AWS_S3_BUCKET)}'}}"
                )
            except ClientError as create_err:
                logger.error(
                    f"[AmazonCloudStorageClient.create] Failed to create bucket | "
                    f"{{'bucket': '{mask_string(settings.AWS_S3_BUCKET)}', 'error': '{str(create_err)}'}}",
                    exc_info=True,
                )
                raise CloudStorageError(create_err) from create_err


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
    def __init__(self, user: UserProjectOrg):
        self.user = user

    def put(self, source: UploadFile, basename: str):
        raise NotImplementedError()

    def stream(self, url: str) -> StreamingBody:
        raise NotImplementedError()


class AmazonCloudStorage(CloudStorage):
    def __init__(self, user: UserProjectOrg):
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
                    "ContentType": source.content_type,
                },
                **kwargs,
            )
            logger.info(
                f"[AmazonCloudStorage.put] File uploaded successfully | "
                f"{{'user_id': '{self.user.id}', 'bucket': '{mask_string(destination.Bucket)}', 'key': '{mask_string(destination.Key)}'}}"
            )
        except ClientError as err:
            logger.error(
                f"[AmazonCloudStorage.put] AWS upload error | "
                f"{{'user_id': '{self.user.id}', 'bucket': '{mask_string(destination.Bucket)}', 'key': '{mask_string(destination.Key)}', 'error': '{str(err)}'}}",
                exc_info=True,
            )
            raise CloudStorageError(f'AWS Error: "{err}"') from err

        return destination

    def stream(self, url: str) -> StreamingBody:
        name = SimpleStorageName.from_url(url)
        kwargs = asdict(name)
        try:
            body = self.aws.client.get_object(**kwargs).get("Body")
            logger.info(
                f"[AmazonCloudStorage.stream] File streamed successfully | "
                f"{{'user_id': '{self.user.id}', 'bucket': '{mask_string(name.Bucket)}', 'key': '{mask_string(name.Key)}'}}"
            )
            return body
        except ClientError as err:
            logger.error(
                f"[AmazonCloudStorage.stream] AWS stream error | "
                f"{{'user_id': '{self.user.id}', 'bucket': '{mask_string(name.Bucket)}', 'key': '{mask_string(name.Key)}', 'error': '{str(err)}'}}",
                exc_info=True,
            )
            raise CloudStorageError(f'AWS Error: "{err}" ({url})') from err

    def get_file_size_kb(self, url: str) -> float:
        name = SimpleStorageName.from_url(url)
        kwargs = asdict(name)
        try:
            response = self.aws.client.head_object(**kwargs)
            size_bytes = response["ContentLength"]
            size_kb = round(size_bytes / 1024, 2)
            logger.info(
                f"[AmazonCloudStorage.get_file_size_kb] File size retrieved successfully | "
                f"{{'user_id': '{self.user.id}', 'bucket': '{mask_string(name.Bucket)}', 'key': '{mask_string(name.Key)}', 'size_kb': {size_kb}}}"
            )
            return size_kb
        except ClientError as err:
            logger.error(
                f"[AmazonCloudStorage.get_file_size_kb] AWS head object error | "
                f"{{'user_id': '{self.user.id}', 'bucket': '{mask_string(name.Bucket)}', 'key': '{mask_string(name.Key)}', 'error': '{str(err)}'}}",
                exc_info=True,
            )
            raise CloudStorageError(f'AWS Error: "{err}" ({url})') from err

    def delete(self, url: str) -> None:
        name = SimpleStorageName.from_url(url)
        kwargs = asdict(name)
        try:
            self.aws.client.delete_object(**kwargs)
            logger.info(
                f"[AmazonCloudStorage.delete] File deleted successfully | "
                f"{{'user_id': '{self.user.id}', 'bucket': '{mask_string(name.Bucket)}', 'key': '{mask_string(name.Key)}'}}"
            )
        except ClientError as err:
            logger.error(
                f"[AmazonCloudStorage.delete] AWS delete error | "
                f"{{'user_id': '{self.user.id}', 'bucket': '{mask_string(name.Bucket)}', 'key': '{mask_string(name.Key)}', 'error': '{str(err)}'}}",
                exc_info=True,
            )
            raise CloudStorageError(f'AWS Error: "{err}" ({url})') from err
