from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    rate_limit_enabled: bool = True
    database_url: str = "postgresql+asyncpg://uploadio:uploadio@localhost:5432/uploadio"
    redis_url: str = "redis://localhost:6379/0"
    frontend_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    token_encryption_key: str = ""
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "uploadio"
    max_upload_bytes: int = 500_000_000
    workspace_quota_bytes: int = 5_000_000_000
    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    instagram_api_version: str = "v24.0"
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_direct_post_enabled: bool = False
    sentry_dsn: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
