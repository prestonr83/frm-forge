from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FRM_FORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_title: str = "FRM Forge"
    host: str = "0.0.0.0"
    port: int = 8088
    db_url: str = "sqlite:///data/frm_forge.db"
    bootstrap_frm_base_url: str = ""
    bootstrap_frm_token: str = ""
    bootstrap_default_schedule_timezone: str = "local"
    bootstrap_refresh_seconds: int = Field(default=10, ge=5, le=300)
    bootstrap_use_websocket: bool = False
    poll_interval_seconds: int = Field(default=10, ge=5, le=300)
    automation_interval_seconds: int = Field(default=15, ge=5, le=300)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
