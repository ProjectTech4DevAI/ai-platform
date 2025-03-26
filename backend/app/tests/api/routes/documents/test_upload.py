import os
import mimetypes
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

import boto3
import pytest
from sqlmodel import Session, select
from moto import mock_aws

from app.core.cloud import AmazonCloudStorageClient
from app.core.config import settings
from app.models import Document
from app.tests.utils.document import (
    Route,
    WebCrawler,
    crawler,
)

def upload(route: Route, scratch: Path, crawler: WebCrawler):
    (mtype, _) = mimetypes.guess_type(str(scratch))
    with scratch.open('rb') as fp:
        return crawler.client.post(
            str(route),
            headers=crawler.superuser_token_headers,
            files={
                'src': (str(scratch), fp, mtype),
            },
        )

@pytest.fixture
def scratch():
    with NamedTemporaryFile(mode='w', suffix='.txt') as fp:
        print('Hello World', file=fp, flush=True)
        yield Path(fp.name)

@pytest.fixture
def route():
    return Route('cp')

@pytest.fixture(scope='class')
def aws_setup():
    os.environ['AWS_ACCESS_KEY_ID']     = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN']    = 'testing'
    os.environ['AWS_SESSION_TOKEN']     = 'testing'
    os.environ['AWS_DEFAULT_REGION']    = settings.AWS_DEFAULT_REGION

@mock_aws
@pytest.mark.usefixtures('aws_setup')
class TestDocumentRouteUpload:
    def test_adds_to_database(
            self,
            db: Session,
            route: Route,
            scratch: Path,
            crawler: WebCrawler,
    ):
        aws = AmazonCloudStorageClient()
        aws.create()

        response = upload(route, scratch, crawler)
        doc_id = (response
                  .json()
                  .get('id'))
        statement = (
            select(Document)
            .where(Document.id == doc_id)
        )
        result = db.exec(statement).one()

        assert result.fname == str(scratch)

    def test_adds_to_S3(
            self,
            route: Route,
            scratch: Path,
            crawler: Route,
    ):
        aws = AmazonCloudStorageClient()
        aws.create()

        response = upload(route, scratch, crawler)
        url = urlparse(response.json().get('object_store_url'))
        key = Path(url.path)
        key = key.relative_to(key.root)

        client = boto3.client('s3')
        assert client.head_object(Bucket=url.netloc, Key=str(key))
