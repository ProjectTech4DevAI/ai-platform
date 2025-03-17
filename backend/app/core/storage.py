from uuid import uuid4
from typing import ClassVar
from pathlib import Path
from dataclasses import dataclass, asdict
from urllib.parse import ParseResult

import boto3
from fastapi import UploadFile
from botocore.exceptions import ClientError

from app.api.deps import CurrentUser

@dataclass(frozen=True)
class SimpleStorageName:
    Bucket: str
    Key: str
    _bucket_delimiter: ClassVar[str] = '-'

    def __init__(self, user: CurrentUser, basename: Path):
        org_proj = (
            user.organization,
            user.project,
        )
        parts = ('_'.join(x.strip().split()) for x in org_proj)
        self.Bucket = self._bucket_delimiter.join(parts)
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
    def put(self, user: CurrentUser, source: UploadFile):
        raise NotImplementedError()

class AmazonCloudStorage(CloudStorage):
    def __init__(self):
        super().__init__()
        self.client = boto3.client('s3')

    def test_and_create(self, target: SimpleStorageName):
        try:
            # does the bucket exist...
            self.client.head_bucket(Bucket=target.Bucket)
        except ClientError as err:
            response = int(err.response['Error']['Code'])
            if response != 404:
                raise
            # ... if not create it
            self.client.create_bucket(Bucket=target.Bucket)

    def put(self, user: CurrentUser, source: UploadFile):
        fname_external = Path(source.filename)
        assert not fname_external.parent.name, 'Source is not a basename'
        destination = SimpleStorageName(user, fname_external)

        kwargs = asdict(destination)
        metadata = user.dict()
        try:
            self.test_and_create(destination)
            self.client.upload_fileobj(
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
