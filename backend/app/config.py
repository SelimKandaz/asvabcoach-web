from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ASVAB Coach API"
    api_prefix: str = "/api"
    database_url: str = Field(
        default="postgresql+psycopg2://asvabcoach:change_me@postgres:5432/asvabcoach",
        alias="DATABASE_URL",
    )
    ai_enabled: bool = Field(default=False, alias="AI_ENABLED")
    ai_api_key: str = Field(default="", alias="AI_API_KEY")
    ai_base_url: str = Field(default="http://host.docker.internal:1234/v1", alias="AI_BASE_URL")
    ai_model: str = Field(default="local-model", alias="AI_MODEL")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )
    cors_origin_regex: str = Field(
        default=r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$",
        alias="CORS_ORIGIN_REGEX",
    )
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    frontend_port: int = Field(default=5173, alias="FRONTEND_PORT")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def data_dir(self) -> Path:
        return Path(__file__).resolve().parent / "data"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def import_log_dir(self) -> Path:
        return self.data_dir / "import_logs"

    @property
    def question_assets_dir(self) -> Path:
        return self.data_dir / "question_assets"

    @property
    def ai_available(self) -> bool:
        return self.ai_enabled and bool(self.ai_base_url.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
