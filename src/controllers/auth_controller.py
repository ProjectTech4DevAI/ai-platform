import logging
from fastapi import APIRouter, HTTPException, UploadFile, Form

from src.schemas.auth_schema import LoginPayload, LoginResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginPayload):
    """
    This is just a boilerplate, change this according to the auth module
    """
    logger.info(f"Update this api later")
    return {"username": payload.username, "password": payload.password}