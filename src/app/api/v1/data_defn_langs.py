from io import StringIO

from fastapi import APIRouter
from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable

from ...models import (
    Post,
    RateLimit,
    Tier,
    User,
)
from ...core.db.database import async_engine
from ...core.exceptions.http_exceptions import NotFoundException

router = APIRouter(tags=['ddls'])

class AlchemyCompiler:
    _models = {
        'post': Post,
        'rate-limit': RateLimit,
        'tier': Tier,
        'user': User,
    }

    def __init__(self, model, engine):
        self.model = model
        self.engine = engine

    def __str__(self):
        return ';\n'.join(self)

    def __iter__(self):
        if self.model not in self._models:
            raise NotFoundException(f'Model "{self.model}" not found')
        yield from map(str, self._compile())

    def _compile(self):
        base = self._models.get(self.model)
        for table in base.metadata.sorted_tables:
            create = CreateTable(table)
            yield create.compile(self.engine)

@router.get('/ddl/{model}')
async def get_ddl(model: str) -> dict:
    engine = create_engine(async_engine.url)
    compiler = AlchemyCompiler(model, engine)

    return {
        'model': model,
        'engine': async_engine.url.drivername,
        'schema':str(compiler),
    }
