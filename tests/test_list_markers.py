"""Focused tests for source-owned list-marker detection and reconstruction."""

from __future__ import annotations

import pytest

from pdftranslate.rendering.list_markers import (
    ListMarker,
    detect_list_marker,
    reconstruct_list_item_text,
)


@pytest.mark.parametrize(
    ("source", "marker", "family"),
    [
        ("• Install the package.", "•", "bullet"),
        ("● Install the package.", "●", "bullet"),
        ("○ Install the package.", "○", "bullet"),
        ("▪ Install the package.", "▪", "bullet"),
        ("- Install the package.", "-", "bullet"),
        ("– Important note", "–", "bullet"),
        ("— Important note", "—", "bullet"),
        ("* Install the package.", "*", "bullet"),
        ("1. Open Settings.", "1.", "numbered"),
        ("1) Open Settings.", "1)", "numbered"),
        ("(1) Open Settings.", "(1)", "numbered"),
        ("a. First option", "a.", "letter"),
        ("a) First option", "a)", "letter"),
        ("(a) First option", "(a)", "letter"),
        ("A. First option", "A.", "letter"),
        ("A) First option", "A)", "letter"),
        ("(A) First option", "(A)", "letter"),
    ],
)
def test_detects_supported_marker_families(source: str, marker: str, family: str) -> None:
    detected = detect_list_marker(source)
    assert detected == ListMarker(
        marker_text=marker,
        family=family,
        separation=" ",
        content_start=len(marker) + 1,
        content_text=source[len(marker) + 1 :],
    )


@pytest.mark.parametrize(
    "source",
    [
        "2026. Annual report",
        "3.14 is pi",
        "-5 °C",
        "12.5 mm",
        "A. Smith",
        "",
        "   ",
    ],
)
def test_fails_closed_on_ambiguous_prefixes(source: str) -> None:
    assert detect_list_marker(source) is None


def test_requires_separation_after_bullet_and_dash() -> None:
    assert detect_list_marker("•Install") is None
    assert detect_list_marker("-Install") is None
    assert detect_list_marker("*Install") is None


def test_reconstructs_marker_with_provider_deleted_marker() -> None:
    assert (
        reconstruct_list_item_text("2) Restart the application.", "Перезапустите приложение.")
        == "2) Перезапустите приложение."
    )


def test_reconstructs_cyrillic_translated_letter_marker() -> None:
    assert reconstruct_list_item_text("a) First option", "а) Первый вариант") == (
        "a) Первый вариант"
    )


def test_reconstruct_strips_restyled_numbered_marker() -> None:
    assert (
        reconstruct_list_item_text("2) Restart the application.", "(2) Перезапустите приложение.")
        == "2) Перезапустите приложение."
    )
    assert (
        reconstruct_list_item_text("2) Restart the application.", "3) Перезапустите приложение.")
        == "2) Перезапустите приложение."
    )


def test_reconstruct_preserves_semantic_content_starting_with_initial() -> None:
    assert (
        reconstruct_list_item_text("• A. Smith is responsible.", "A. Smith is responsible.")
        == "• A. Smith is responsible."
    )


def test_reconstructs_marker_with_provider_translated_marker() -> None:
    assert (
        reconstruct_list_item_text("2) Restart the application.", "2. Перезапустите приложение.")
        == "2) Перезапустите приложение."
    )


def test_reconstructs_marker_with_provider_duplicated_marker() -> None:
    assert (
        reconstruct_list_item_text(
            "2) Restart the application.",
            "2) 2) Перезапустите приложение.",
        )
        == "2) Перезапустите приложение."
    )


def test_reconstructs_bullet_and_preserves_separation() -> None:
    assert (
        reconstruct_list_item_text("•  Install the package.", "Установите пакет.")
        == "•  Установите пакет."
    )


def test_reconstruct_returns_none_for_ambiguous_source() -> None:
    assert reconstruct_list_item_text("2026. Annual report", "Годовой отчёт.") is None


def test_reconstruct_returns_none_when_no_content_remains() -> None:
    assert reconstruct_list_item_text("2) Restart the application.", "2)") is None


def test_reconstruct_strips_translated_bullet_restyle() -> None:
    assert (
        reconstruct_list_item_text("• Install the package.", "- Установите пакет.")
        == "• Установите пакет."
    )


def test_reconstruct_strips_translated_bullet_before_semantic_initial() -> None:
    result = reconstruct_list_item_text("• A. Smith is responsible.", "- A. Smith is responsible.")
    assert result == "• A. Smith is responsible."
    assert result.count("•") == 1


def test_reconstruct_preserves_semantic_prefix_absent_from_source() -> None:
    assert reconstruct_list_item_text("1. First option", "A. First option") == "1. A. First option"
