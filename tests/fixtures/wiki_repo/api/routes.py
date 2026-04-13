"""API route definitions."""

from fastapi import FastAPI, HTTPException

from .schema import WikiPage, CreatePageRequest


def register_routes(app: FastAPI) -> None:
    """Register all API routes."""

    @app.get("/pages/{page_id}")
    def get_page(page_id: str) -> WikiPage:
        # TODO: fetch from database
        return WikiPage(id=page_id, title="Sample", content="")

    @app.post("/pages")
    def create_page(request: CreatePageRequest) -> WikiPage:
        return WikiPage(id="new", title=request.title, content=request.content)

    @app.get("/health")
    def health_check() -> dict:
        return {"status": "ok"}
