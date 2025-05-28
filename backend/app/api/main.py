from fastapi import APIRouter

from app.api.routes import (
    api_keys,
    collections,
    documents,
    login,
    organization,
    project,
    project_user,
    private,
    threads,
    users,
    utils,
    onboarding,
    credentials,
    evaluation,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(api_keys.router)
api_router.include_router(collections.router)
api_router.include_router(credentials.router)
api_router.include_router(documents.router)
api_router.include_router(evaluation.router)
api_router.include_router(login.router)
api_router.include_router(onboarding.router)
api_router.include_router(organization.router)
api_router.include_router(project.router)
api_router.include_router(project_user.router)
api_router.include_router(threads.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)

if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
