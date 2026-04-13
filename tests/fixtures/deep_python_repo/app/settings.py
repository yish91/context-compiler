import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key")
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///db.sqlite3")
