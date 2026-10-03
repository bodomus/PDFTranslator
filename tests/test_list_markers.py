"""Focused tests for source-owned list-marker detection and reattachment."""

from __future__ import annotations

import pytest

from pdftranslate.list_markers import (
    ListMarker,
    detect_list_marker,
    reattach_list_marker,
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


def test_detects_semantic_content_after_marker() -> None:
    marker = detect_list_marker("a) A. Smith is responsible.")
    assert marker is not None
    assert marker.marker_text == "a)"
    assert marker.content_text == "A. Smith is responsible."


def test_reattaches_source_marker_to_semantic_text() -> None:
    assert (
        reattach_list_marker("2) Restart the application.", "Перезапустите приложение.")
        == "2) Перезапустите приложение."
    )


def test_reattach_preserves_semantic_initial() -> None:
    # The semantic "A." is translated content, never structural.
    assert reattach_list_marker("a) A. Smith is responsible.", "A. Smith отвечает.") == (
        "a) A. Smith отвечает."
    )


def test_reattach_preserves_numeric_semantic_prefix() -> None:
    assert reattach_list_marker("• 1.5 mm tolerance is required.", "1.5 мм допуска.") == (
        "• 1.5 мм допуска."
    )


def test_reattach_preserves_source_separation() -> None:
    assert reattach_list_marker("•  Install the package.", "Установите пакет.") == (
        "•  Установите пакет."
    )


def test_reattach_returns_none_for_ambiguous_source() -> None:
    assert reattach_list_marker("2026. Annual report", "Годовой отчёт.") is None


def test_reattach_returns_none_when_no_content_remains() -> None:
    assert reattach_list_marker("2) Restart the application.", "") is None
    assert reattach_list_marker("2) Restart the application.", "   ") is None
