from fastapi import APIRouter

from app.api.routes import (
    api_keys,
    assistants,
    collections,
    documents,
    doc_transformation_job,
    login,
    organization,
    openai_conversation,
    project,
    project_user,
    responses,
    private,
    threads,
    users,
    utils,
    onboarding,
    credentials,
    fine_tuning,
    model_evaluation,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(api_keys.router)
api_router.include_router(assistants.router)
api_router.include_router(collections.router)
api_router.include_router(credentials.router)
api_router.include_router(documents.router)
api_router.include_router(doc_transformation_job.router)
api_router.include_router(login.router)
api_router.include_router(onboarding.router)
api_router.include_router(openai_conversation.router)
api_router.include_router(organization.router)
api_router.include_router(project.router)
api_router.include_router(project_user.router)
api_router.include_router(responses.router)
api_router.include_router(threads.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(fine_tuning.router)
api_router.include_router(model_evaluation.router)


if settings.ENVIRONMENT in ["development", "testing"]:
    api_router.include_router(private.router)
