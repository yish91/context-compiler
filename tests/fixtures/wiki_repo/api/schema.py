"""Data models for the Wiki API."""

from pydantic import BaseModel


class WikiPage(BaseModel):
    """Represents a wiki page."""
    id: str
    title: str
    content: str


class CreatePageRequest(BaseModel):
    """Request body for creating a new page."""
    title: str
    content: str


class User(BaseModel):
    """Represents an authenticated user."""
    id: str
    username: str
    email: str
