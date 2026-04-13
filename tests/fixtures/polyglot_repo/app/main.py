"""Application bootstrap."""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class User(BaseModel):
    id: int
    email: str


def bootstrap() -> FastAPI:
    return app


@app.get("/health")
def health() -> dict[str, str]:
    return {"ok": "true"}


@app.get("/users")
def list_users() -> list[User]:
    return []
