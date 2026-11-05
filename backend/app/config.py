import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root or backend folder
backend_dir = Path(__file__).resolve().parent.parent
project_root = backend_dir.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv(backend_dir / ".env")


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-pharma-predict-secret-key-change-in-prod-2026")
    ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = False
    TESTING = False

    # Database
    # Support PostgreSQL / TimescaleDB with SQLite fallback for lightweight development
    DEFAULT_SQLITE_PATH = project_root / "pharmapredict_dev.db"
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
    )
    # Fix potential postgres:// vs postgresql:// protocol in older connection strings
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    } if not SQLALCHEMY_DATABASE_URI.startswith("sqlite") else {}

    # CORS
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if origin.strip()
    ]

    # Application details
    API_PREFIX = "/api/v1"
    APP_NAME = "PharmaPredict AI"
    APP_VERSION = "0.1.0"


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

