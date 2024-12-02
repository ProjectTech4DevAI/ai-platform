from fastapi import APIRouter
from src.auth.controller import router as auth_router
from src.llm.controller import router as llm_router
from src.document_manager.controller import router as document_manager_router

internal_router = APIRouter()

# mount all api endpoints here
internal_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
internal_router.include_router(llm_router, prefix="/llm", tags=["LLM"])
internal_router.include_router(
    document_manager_router, prefix="/document", tags=["Document Manager"]
)
