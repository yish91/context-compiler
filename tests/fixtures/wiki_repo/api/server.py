"""Wiki API server entrypoint."""

import os

from fastapi import FastAPI

from .routes import register_routes
from .schema import WikiPage

app = FastAPI(title=os.getenv("APP_NAME", "Wiki API"))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    register_routes(app)
    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)
