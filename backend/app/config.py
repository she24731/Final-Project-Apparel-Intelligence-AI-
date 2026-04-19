from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias="GEMINI_MODEL")
    # Veo model id for generate_videos (see Google AI “Generate videos” docs; override via GEMINI_VIDEO_MODEL).
    gemini_video_model: str = Field(default="veo-3.1-generate-preview", validation_alias="GEMINI_VIDEO_MODEL")
    runway_api_key: str | None = Field(default=None, validation_alias="RUNWAY_API_KEY")
    media_provider: str = Field(default="mock", validation_alias="MEDIA_PROVIDER")
    backend_host: str = Field(default="127.0.0.1", validation_alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, validation_alias="BACKEND_PORT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CORS_ORIGINS",
    )
    data_dir: Path = Field(default=Path("./data"), validation_alias="DATA_DIR")

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def generated_media_dir(self) -> Path:
        return self.data_dir / "generated_media"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def has_live_llm(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.strip())

    @property
    def pydantic_ai_model(self) -> str:
        """
        PydanticAI model string.

        We default to Gemini via the google provider format.
        """
        return f"google-gla:{self.gemini_model}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
