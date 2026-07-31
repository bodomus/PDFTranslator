"""Typed application settings."""

from pathlib import Path

from platformdirs import user_cache_path, user_config_path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_cache_dir() -> Path:
    return user_cache_path("PDFTranslate", appauthor=False)


def _default_config_dir() -> Path:
    return user_config_path("PDFTranslate", appauthor=False)


class Settings(BaseSettings):
    """Settings read from defaults and PDFTRANSLATE_ environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="PDFTRANSLATE_",
        case_sensitive=False,
        extra="ignore",
    )

    log_level: str = "INFO"
    cache_dir: Path = Field(default_factory=_default_cache_dir)
    config_dir: Path = Field(default_factory=_default_config_dir)
