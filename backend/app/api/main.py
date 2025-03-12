from fastapi import APIRouter


from app.api.routes import items, login, private, users, utils,ai_assistant_controller,health,thread,Organization, Project, project_user

from app.core.config import settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(Organization.router)
api_router.include_router(Project.router)
api_router.include_router(ai_assistant_controller.router)
api_router.include_router(thread.router)
api_router.include_router(project_user.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)



