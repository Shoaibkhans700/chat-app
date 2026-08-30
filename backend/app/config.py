"""
Application configuration.

All values are read from environment variables so that nothing is
hard-coded. In docker-compose these come from the `environment:` block;
in Kubernetes they come from a ConfigMap (non-secret values) and a
Secret (DB_USERNAME, DB_PASSWORD, JWT_SECRET_KEY).
"""
import os
from functools import lru_cache


class Settings:
    # --- Database ---
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "chatapp")
    DB_USERNAME: str = os.getenv("DB_USERNAME", "chatapp")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "chatapp")

    # --- Auth ---
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

    # --- CORS (comma separated list of allowed origins) ---
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USERNAME}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
