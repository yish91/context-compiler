"""Runtime configuration.

This module centralizes every environment-driven setting the API reads
at startup. Keeping all os.environ access in one place makes it easy
for the context compiler to enumerate the real configuration surface
without having to scan the rest of the codebase.

The Settings class is intentionally simple. Production code would
likely use pydantic-settings or a similar library, but the fixture
avoids that dependency so the test repo stays small.
"""

import os


class Settings:
    """Typed view over the environment variables the API consumes."""

    def __init__(self) -> None:
        self.app_name = os.environ.get("APP_NAME", "medium-api")
        self.database_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
        self.secret_key = os.environ.get("SECRET_KEY", "dev")
        self.log_level = os.environ.get("LOG_LEVEL", "info")
        self.feature_flags = os.environ.get("FEATURE_FLAGS", "")
        self.sentry_dsn = os.environ.get("SENTRY_DSN", "")
        self.allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*")


settings = Settings()
