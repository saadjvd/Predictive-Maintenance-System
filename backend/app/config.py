import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env.local first, followed by .env (standard 12-factor / Next.js convention)
# Existing OS/container/platform environment variables always take precedence (override=False)
backend_dir = Path(__file__).resolve().parent.parent
project_root = backend_dir.parent

for env_candidate in [
    project_root / ".env.local",
    backend_dir / ".env.local",
    project_root / ".env",
    backend_dir / ".env",
]:
    if env_candidate.exists():
        load_dotenv(env_candidate, override=False)

DEFAULT_DEV_SECRET = "dev-pharma-predict-secret-key-change-in-prod-2026"


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_DEV_SECRET)
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
    if SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.strip().strip("'\"")
    # Fix potential postgres:// vs postgresql:// protocol in older connection strings
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    } if not SQLALCHEMY_DATABASE_URI.startswith("sqlite") else {}

    # Redis URL for task queuing and telemetry caching
    REDIS_URL = os.getenv("REDIS_URL", None)

    # Database migration controls
    AUTO_MIGRATE = os.getenv("AUTO_MIGRATE", "false").lower() in ("true", "1", "yes")
    ENFORCE_MIGRATION_CHECK = os.getenv("ENFORCE_MIGRATION_CHECK", "false").lower() in ("true", "1", "yes")
    SKIP_STARTUP_MIGRATION_CHECK = os.getenv("SKIP_STARTUP_MIGRATION_CHECK", "false").lower() in ("true", "1", "yes")
    SKIP_DB_CREATE_ALL = os.getenv("SKIP_DB_CREATE_ALL", "false").lower() in ("true", "1", "yes")

    # CORS origins (Restricted to exact production domains and local development)
    default_cors = "https://cold-wood-def2.saadjvd54.workers.dev,https://pharmapredict-ai.pages.dev,http://localhost:3000,http://127.0.0.1:3000"
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", default_cors).split(",")
        if origin.strip()
    ]

    # Application details
    API_PREFIX = "/api/v1"
    APP_NAME = "PharmaPredict AI"
    APP_VERSION = "1.0.0"


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    ENV = "development"


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    ENV = "testing"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    AUTO_MIGRATE = False
    ENFORCE_MIGRATION_CHECK = False


class StagingConfig(Config):
    """Staging / Pre-production configuration."""
    DEBUG = False
    TESTING = False
    ENV = "staging"
    ENFORCE_MIGRATION_CHECK = True

    @classmethod
    def validate(cls):
        """Validate staging configuration."""
        if cls.SECRET_KEY == DEFAULT_DEV_SECRET or not cls.SECRET_KEY or len(cls.SECRET_KEY) < 16:
            raise ValueError(
                "Staging environment requires a secure SECRET_KEY (cannot use default dev key, min 16 chars)."
            )


class ProductionConfig(Config):
    """Production configuration with strict pharmaceutical validation."""
    DEBUG = False
    TESTING = False
    ENV = "production"
    ENFORCE_MIGRATION_CHECK = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    @classmethod
    def validate(cls):
        """Strict validation of production secrets and database configuration."""
        if cls.SECRET_KEY == DEFAULT_DEV_SECRET or not cls.SECRET_KEY or len(cls.SECRET_KEY) < 32:
            raise ValueError(
                "Production environment requires a strong, cryptographically random SECRET_KEY "
                "(cannot use default dev key, minimum 32 characters)."
            )

        if cls.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
            raise ValueError(
                "Production environment requires an enterprise database (PostgreSQL / TimescaleDB). "
                "SQLite is prohibited in production deployments."
            )


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "staging": StagingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
