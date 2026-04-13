"""Authentication module for the Wiki API."""

import os
from datetime import datetime, timedelta

from pydantic import BaseModel


AUTH_SECRET = os.getenv("AUTH_SECRET", "changeme")
AUTH_TOKEN_EXPIRY = int(os.getenv("AUTH_TOKEN_EXPIRY", "3600"))


class AuthToken(BaseModel):
    """Represents an authentication token."""
    token: str
    user_id: str
    expires_at: datetime


class AuthCredentials(BaseModel):
    """Login credentials."""
    username: str
    password: str


def create_auth_token(user_id: str) -> AuthToken:
    """Create an auth token for a user."""
    import secrets
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(seconds=AUTH_TOKEN_EXPIRY)
    return AuthToken(token=token, user_id=user_id, expires_at=expires)


def verify_auth_token(token: str) -> bool:
    """Verify that a token is valid."""
    # TODO: implement actual verification
    return True
