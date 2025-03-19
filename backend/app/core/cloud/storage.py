import functools as ft
from uuid import uuid4
from typing import ClassVar
from pathlib import Path
from dataclasses import dataclass, asdict
from urllib.parse import ParseResult

import boto3
from fastapi import UploadFile
from botocore.exceptions import ClientError

from app.api.deps import CurrentUser
from app.core.config import settings

class AmazonCloudStorageClient:
    @ft.cached_property
    def client(self):
        return boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_DEFAULT_REGION,
        )

@dataclass(frozen=True)
class SimpleStorageName:
    Bucket: str
    Key: str

    def __init__(self, basename: Path):
        self.Bucket = settings.AWS_S3_BUCKET
        self.Key = str(basename.with_name(str(uuid4())))

    def to_url(self):
        kwargs = {
            'scheme': 's3',
            'netloc': self.Bucket,
            'path': self.Key,
        }
        for k in ParseResult._fields:
            kwargs.setdefault(k)

        return ParseResult(**kwargs)

class CloudStorage:
    def __init__(self, user: CurrentUser):
        self.user = user

    def put(self, source: UploadFile):
        raise NotImplementedError()

class AmazonCloudStorage(CloudStorage):
    def __init__(self, user: CurrentUser):
        super().__init__(user)
        self.aws = AmazonCloudStorageClient()

    def put(self, source: UploadFile):
        fname_external = Path(source.filename)
        assert not fname_external.parent.name, 'Source is not a basename'
        destination = SimpleStorageName(fname_external)

        kwargs = asdict(destination)
        metadata = self.user.dict()
        try:
            self.aws.client.upload_fileobj(
                source.file,
                ExtraArgs={
                    'Metadata': metadata,
                    'ContentType': source.content_type,
                },
                **kwargs,
            )
        except ClientError as err:
            raise ConnectionError(f'AWS Error: "{err}"') from err

        return destination.to_url()
