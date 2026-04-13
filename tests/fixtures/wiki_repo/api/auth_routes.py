"""Auth route definitions."""

from fastapi import FastAPI, HTTPException

from .auth import AuthCredentials, AuthToken, create_auth_token, verify_auth_token
from .schema import User


def register_auth_routes(app: FastAPI) -> None:
    """Register authentication API routes."""

    @app.post("/auth/login")
    def login(credentials: AuthCredentials) -> AuthToken:
        # TODO: verify credentials against database
        if credentials.username and credentials.password:
            return create_auth_token(user_id="user123")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    @app.post("/auth/logout")
    def logout() -> dict:
        return {"status": "logged_out"}

    @app.get("/auth/me")
    def get_current_user() -> User:
        # TODO: get user from token
        return User(id="user123", username="testuser", email="test@example.com")
