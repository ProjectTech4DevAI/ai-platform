from datetime import datetime

from fastapi import APIRouter

router = APIRouter(tags=['heartbeat'])

@router.get('/hello')
async def check_heartbeat() -> dict:
    return {
        'hello': datetime.now().strftime('%c'),
    }
