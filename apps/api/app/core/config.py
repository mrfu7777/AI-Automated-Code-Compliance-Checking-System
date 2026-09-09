from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Automated Code Compliance Checking System"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    api_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    database_url: str = (
        "postgresql+asyncpg://code_compliance:change-me@localhost:5432/code_compliance"
    )
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    minio_endpoint: str = "localhost:9000"
    minio_public_endpoint: str = "localhost:9000"
    minio_access_key: str = "code-compliance"
    minio_secret_key: str = "change-me-minio-password"
    minio_bucket: str = "code-compliance"
    minio_secure: bool = False
    max_upload_size_bytes: int = 157_286_400
    default_organization_id: str = "00000000-0000-0000-0000-000000000001"
    default_user_id: str = "00000000-0000-0000-0000-000000000002"


@lru_cache
def get_settings() -> Settings:
    return Settings()
