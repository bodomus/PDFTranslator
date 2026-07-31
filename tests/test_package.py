from pathlib import Path

import pytest

import pdftranslate
from pdftranslate.config import Settings
from pdftranslate.logging_config import SUPPORTED_LOG_LEVELS, configure_logging


def test_package_imports_with_expected_version() -> None:
    assert pdftranslate.__version__ == "0.1.0"


def test_default_settings_paths_are_paths() -> None:
    settings = Settings()

    assert isinstance(settings.cache_dir, Path)
    assert isinstance(settings.config_dir, Path)


def test_settings_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    cache_dir = Path("test-cache")
    config_dir = Path("test-config")
    monkeypatch.setenv("PDFTRANSLATE_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("PDFTRANSLATE_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("PDFTRANSLATE_LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.cache_dir == cache_dir
    assert settings.config_dir == config_dir
    assert settings.log_level == "DEBUG"


@pytest.mark.parametrize("level", sorted(SUPPORTED_LOG_LEVELS))
def test_logging_accepts_supported_levels(level: str) -> None:
    configure_logging(level)


def test_logging_rejects_unsupported_level() -> None:
    with pytest.raises(ValueError, match="Unsupported log level"):
        configure_logging("TRACE")
