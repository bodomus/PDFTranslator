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
    classification_min_text_characters: int = Field(default=20, ge=1)
    classification_max_incidental_text_blocks: int = Field(default=1, ge=0)
    classification_mixed_image_area_ratio: float = Field(default=0.15, ge=0, le=1)
    classification_scanned_image_area_ratio: float = Field(default=0.65, ge=0, le=1)
