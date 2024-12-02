import logging
from fastapi import APIRouter, Depends, Request

from src.middlewares.auth_middleware import auth_middleware

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def boilerplate(
    request: Request,
):
    """
    Boilerplate
    """
    body = request.query_params
    logger.info(body)
    return {"success": 1, "state": request.state.foo}
