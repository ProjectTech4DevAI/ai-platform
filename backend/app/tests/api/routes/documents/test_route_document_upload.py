import os
import mimetypes
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

import pytest
from moto import mock_aws
from sqlmodel import Session, select
from fastapi.testclient import TestClient

from app.core.cloud import AmazonCloudStorageClient
from app.core.config import settings
from app.models import Document
from app.tests.utils.document import Route, WebCrawler, httpx_to_standard


class WebUploader(WebCrawler):
    def put(self, route: Route, scratch: Path):
        (mtype, _) = mimetypes.guess_type(str(scratch))
        with scratch.open("rb") as fp:
            return self.client.post(
                str(route),
                headers=self.user_api_key_header,
                files={
                    "src": (str(scratch), fp, mtype),
                },
            )


@pytest.fixture
def scratch():
    with NamedTemporaryFile(mode="w", suffix=".txt") as fp:
        print("Hello World", file=fp, flush=True)
        yield Path(fp.name)


@pytest.fixture
def route():
    return Route("upload")


@pytest.fixture
def uploader(client: TestClient, user_api_key_header: dict[str, str]):
    return WebUploader(client, user_api_key_header)


@pytest.fixture(scope="class")
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = settings.AWS_DEFAULT_REGION


@mock_aws
@pytest.mark.usefixtures("aws_credentials")
class TestDocumentRouteUpload:
    def test_adds_to_database(
        self,
        db: Session,
        route: Route,
        scratch: Path,
        uploader: WebUploader,
    ):
        aws = AmazonCloudStorageClient()
        aws.create()

        response = httpx_to_standard(uploader.put(route, scratch))
        doc_id = response.data["id"]
        statement = select(Document).where(Document.id == doc_id)
        result = db.exec(statement).one()

        assert result.fname == str(scratch)

    def test_adds_to_S3(
        self,
        route: Route,
        scratch: Path,
        uploader: WebUploader,
    ):
        aws = AmazonCloudStorageClient()
        aws.create()

        response = httpx_to_standard(uploader.put(route, scratch))
        url = urlparse(response.data["object_store_url"])
        key = Path(url.path)
        key = key.relative_to(key.root)

        assert aws.client.head_object(Bucket=url.netloc, Key=str(key))
