import logging
import uvicorn
from fastapi import FastAPI, Depends
from src.config.env_settings import get_settings, Settings
from src.config.logging_config import setup_logging
from src.routes import internal_router


setup_logging()
logger = logging.getLogger(__name__)
app = FastAPI(title="T4D AI Service", docs_url="/api/docs", redoc_url="/api/redoc")


@app.get("/api", tags=["Health"])
async def health(settings: Settings = Depends(get_settings)):
    return {"res": "T4D's AI service running on port " + str(settings.SERVER_PORT)}


app.include_router(internal_router, prefix="/api")

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",host="127.0.0.1",port=(settings.SERVER_PORT or 7050),reload=settings.APP_ENV == "dev",reload_dirs=["src", "tests"],
    )
