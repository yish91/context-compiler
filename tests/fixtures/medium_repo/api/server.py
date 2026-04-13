"""API server bootstrap."""

from fastapi import FastAPI

from .config import settings
from .routes import register_routes

app = FastAPI(title=settings.app_name)


def bootstrap() -> FastAPI:
    register_routes(app)
    return app
