from fastapi import APIRouter

router = APIRouter(tags=['ddls'])

@router.get('/ddl/{model}')
async def get_ddl(model: str) -> dict:
    return {
        'hello': model,
    }
