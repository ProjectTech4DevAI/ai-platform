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

from app.api.deps import CurrentUser
from app.core.config import settings

logger = logging.getLogger(__name__)


class CloudStorageError(Exception):
    pass


class AmazonCloudStorageClient:
    @ft.cached_property
    def client(self):
        logger.info(
            f"[AmazonCloudStorageClient.client] Initializing S3 client | {{'region': '{settings.AWS_DEFAULT_REGION}'}}"
        )
        kwargs = {}
        cred_params = (
            ("aws_access_key_id", "AWS_ACCESS_KEY_ID"),
            ("aws_secret_access_key", "AWS_SECRET_ACCESS_KEY"),
            ("region_name", "AWS_DEFAULT_REGION"),
        )

        for i, j in cred_params:
            kwargs[i] = os.environ.get(j, getattr(settings, j))

        client = boto3.client("s3", **kwargs)
        logger.info(
            f"[AmazonCloudStorageClient.client] S3 client initialized | {{'region': '{settings.AWS_DEFAULT_REGION}'}}"
        )
        return client

    def create(self):
        logger.info(
            f"[AmazonCloudStorageClient.create] Checking/creating S3 bucket | {{'bucket': '{settings.AWS_S3_BUCKET}'}}"
        )
        try:
            # does the bucket exist...
            self.client.head_bucket(Bucket=settings.AWS_S3_BUCKET)
            logger.info(
                f"[AmazonCloudStorageClient.create] Bucket exists | {{'bucket': '{settings.AWS_S3_BUCKET}'}}"
            )
        except ValueError as err:
            logger.error(
                f"[AmazonCloudStorageClient.create] Invalid bucket configuration | {{'bucket': '{settings.AWS_S3_BUCKET}', 'error': '{str(err)}'}}"
            )
            raise CloudStorageError(err) from err
        except ClientError as err:
            response = int(err.response["Error"]["Code"])
            if response != 404:
                logger.error(
                    f"[AmazonCloudStorageClient.create] Unexpected AWS error | {{'bucket': '{settings.AWS_S3_BUCKET}', 'error': '{str(err)}', 'code': {response}}}"
                )
                raise CloudStorageError(err) from err
            # ... if not create it
            logger.warning(
                f"[AmazonCloudStorageClient.create] Bucket not found, creating | {{'bucket': '{settings.AWS_S3_BUCKET}'}}"
            )
            try:
                self.client.create_bucket(
                    Bucket=settings.AWS_S3_BUCKET,
                    CreateBucketConfiguration={
                        "LocationConstraint": settings.AWS_DEFAULT_REGION,
                    },
                )
                logger.info(
                    f"[AmazonCloudStorageClient.create] Bucket created successfully | {{'bucket': '{settings.AWS_S3_BUCKET}'}}"
                )
            except ClientError as create_err:
                logger.error(
                    f"[AmazonCloudStorageClient.create] Failed to create bucket | {{'bucket': '{settings.AWS_S3_BUCKET}', 'error': '{str(create_err)}'}}"
                )
                raise CloudStorageError(create_err) from create_err


@dataclass(frozen=True)
class SimpleStorageName:
    Key: str
    Bucket: str = settings.AWS_S3_BUCKET

    def __str__(self):
        return urlunparse(self.to_url())

    def to_url(self):
        logger.info(
            f"[SimpleStorageName.to_url] Generating S3 URL | {{'bucket': '{self.Bucket}', 'key': '{self.Key}'}}"
        )
        kwargs = {
            "scheme": "s3",
            "netloc": self.Bucket,
            "path": self.Key,
        }
        for k in ParseResult._fields:
            kwargs.setdefault(k)

        url = ParseResult(**kwargs)
        logger.info(
            f"[SimpleStorageName.to_url] S3 URL generated | {{'url': '{urlunparse(url)}'}}"
        )
        return url

    @classmethod
    def from_url(cls, url: str):
        logger.info(
            f"[SimpleStorageName.from_url] Parsing S3 URL | {{'url': '{url}'}}"
        )
        url = urlparse(url)
        path = Path(url.path)
        if path.is_absolute():
            path = path.relative_to(path.root)

        instance = cls(Bucket=url.netloc, Key=str(path))
        logger.info(
            f"[SimpleStorageName.from_url] URL parsed successfully | {{'bucket': '{instance.Bucket}', 'key': '{instance.Key}'}}"
        )
        return instance


class CloudStorage:
    def __init__(self, user: CurrentUser):
        self.user = user
        logger.info(
            f"[CloudStorage.init] Initialized CloudStorage | {{'user_id': '{user.id}'}}"
        )

    def put(self, source: UploadFile, basename: str):
        raise NotImplementedError()

    def stream(self, url: str) -> StreamingBody:
        raise NotImplementedError()


class AmazonCloudStorage(CloudStorage):
    def __init__(self, user: CurrentUser):
        super().__init__(user)
        self.aws = AmazonCloudStorageClient()
        logger.info(
            f"[AmazonCloudStorage.init] Initialized AmazonCloudStorage | {{'user_id': '{user.id}'}}"
        )

    def put(self, source: UploadFile, basename: Path) -> SimpleStorageName:
        logger.info(
            f"[AmazonCloudStorage.put] Starting file upload | {{'user_id': '{self.user.id}', 'filename': '{source.filename}', 'basename': '{basename}'}}"
        )
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
            logger.info(
                f"[AmazonCloudStorage.put] File uploaded successfully | {{'user_id': '{self.user.id}', 'bucket': '{destination.Bucket}', 'key': '{destination.Key}'}}"
            )
        except ClientError as err:
            logger.error(
                f"[AmazonCloudStorage.put] AWS upload error | {{'user_id': '{self.user.id}', 'bucket': '{destination.Bucket}', 'key': '{destination.Key}', 'error': '{str(err)}'}}"
            )
            raise CloudStorageError(f'AWS Error: "{err}"') from err

        return destination

    def stream(self, url: str) -> StreamingBody:
        logger.info(
            f"[AmazonCloudStorage.stream] Starting file stream | {{'user_id': '{self.user.id}', 'url': '{url}'}}"
        )
        name = SimpleStorageName.from_url(url)
        kwargs = asdict(name)
        try:
            body = self.aws.client.get_object(**kwargs).get("Body")
            logger.info(
                f"[AmazonCloudStorage.stream] File streamed successfully | {{'user_id': '{self.user.id}', 'bucket': '{name.Bucket}', 'key': '{name.Key}'}}"
            )
            return body
        except ClientError as err:
            raise CloudStorageError(f'AWS Error: "{err}" ({url})') from err

    def get_file_size_kb(self, url: str) -> float:
        name = SimpleStorageName.from_url(url)
        kwargs = asdict(name)
        response = self.aws.client.head_object(**kwargs)
        size_bytes = response["ContentLength"]
        return round(size_bytes / 1024, 2)

    def delete(self, url: str) -> None:
        name = SimpleStorageName.from_url(url)
        kwargs = asdict(name)
        try:
            self.aws.client.delete_object(**kwargs)
        except ClientError as err:
            raise CloudStorageError(f'AWS Error: "{err}" ({url})') from err
