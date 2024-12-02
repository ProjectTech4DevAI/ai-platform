import pytest

# from httpx import AsyncClient
from main import app


@pytest.mark.asyncio
async def test_read_root():
    assert True
