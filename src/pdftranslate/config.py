"""Typed application settings."""

from pathlib import Path
from typing import Literal

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
    paragraph_reconstruction_mode: Literal["conservative", "off"] = "conservative"
    paragraph_left_alignment_tolerance: float = Field(default=8.0, gt=0)
    paragraph_indentation_tolerance: float = Field(default=14.0, gt=0)
    paragraph_max_vertical_gap_ratio: float = Field(default=0.75, gt=0)
    paragraph_min_width_ratio: float = Field(default=0.72, gt=0, le=1)
    paragraph_column_gutter_ratio: float = Field(default=0.08, gt=0, le=1)
    paragraph_heading_font_ratio: float = Field(default=1.18, gt=0)
    paragraph_footnote_font_ratio: float = Field(default=0.82, gt=0, le=1)
    paragraph_margin_region_ratio: float = Field(default=0.12, gt=0, le=1)
    paragraph_cross_page_edge_ratio: float = Field(default=0.18, gt=0, le=1)
    paragraph_repeated_margin_min_pages: int = Field(default=2, ge=2)
    repeated_elements_mode: Literal["auto", "off"] = "auto"
    repeated_margin_region_ratio: float = Field(default=0.12, gt=0, le=1)
    repeated_min_recurrence_ratio: float = Field(default=0.60, gt=0, le=1)
    repeated_parity_recurrence_ratio: float = Field(default=0.75, gt=0, le=1)
    repeated_bbox_tolerance_ratio: float = Field(default=0.035, gt=0, le=1)
    repeated_font_size_tolerance_ratio: float = Field(default=0.18, gt=0, le=1)
    repeated_watermark_font_ratio: float = Field(default=1.60, gt=1)
    repeated_min_confirmed_pages: int = Field(default=3, ge=3)
