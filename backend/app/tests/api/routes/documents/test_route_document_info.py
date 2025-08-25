import pytest
from sqlmodel import Session

from app.crud import get_project_by_id
from app.tests.utils.document import (
    DocumentComparator,
    DocumentMaker,
    DocumentStore,
    Route,
    WebCrawler,
    crawler,
    httpx_to_standard,
)


@pytest.fixture
def route():
    return Route("info")


class TestDocumentRouteInfo:
    def test_response_is_success(
        self,
        db: Session,
        route: Route,
        crawler: WebCrawler,
    ):
        project = get_project_by_id(
            session=db, project_id=crawler.user_api_key.project_id
        )
        store = DocumentStore(db=db, project=project)
        response = crawler.get(route.append(store.put()))

        assert response.is_success

    def test_info_reflects_database(
        self,
        db: Session,
        route: Route,
        crawler: WebCrawler,
    ):
        project = get_project_by_id(
            session=db, project_id=crawler.user_api_key.project_id
        )
        store = DocumentStore(db=db, project=project)
        document = store.put()
        source = DocumentComparator(document)

        target = httpx_to_standard(crawler.get(route.append(document)))

        assert source == target.data

    def test_cannot_info_unknown_document(
        self, db: Session, route: Route, crawler: Route
    ):
        DocumentStore.clear(db)
        project = get_project_by_id(
            session=db, project_id=crawler.user_api_key.project_id
        )
        maker = DocumentMaker(project=project)
        response = crawler.get(route.append(next(maker)))

        assert response.is_error
