from fastapi import APIRouter
from src.controllers.auth_controller import router as auth_router

internal_router = APIRouter()

# mount all api endpoints here
internal_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
