"""Role-aware adapters from reconstructed typography to the reflow contract."""

from __future__ import annotations

from pdftranslate.rendering.reflow.models import ReflowAlignment, ReflowStyle
from pdftranslate.typography import ResolvedParagraphStyle, TextAlignment, TypographyRole

_ALIGNMENT = {
    TextAlignment.LEFT: ReflowAlignment.LEFT,
    TextAlignment.CENTER: ReflowAlignment.CENTER,
    TextAlignment.RIGHT: ReflowAlignment.RIGHT,
    TextAlignment.JUSTIFIED: ReflowAlignment.JUSTIFIED,
}


def body_reflow_style(
    resolved: ResolvedParagraphStyle,
) -> tuple[ReflowStyle, tuple[float, float, float]]:
    """Return the applied BODY style and normalized renderer color."""
    return _resolved_reflow_style(resolved, expected_role=TypographyRole.BODY, heading=False)


def heading_reflow_style(
    resolved: ResolvedParagraphStyle,
) -> tuple[ReflowStyle, tuple[float, float, float]]:
    """Return the applied HEADING style and normalized renderer color."""
    return _resolved_reflow_style(resolved, expected_role=TypographyRole.HEADING, heading=True)


def footnote_reflow_style(
    resolved: ResolvedParagraphStyle,
) -> tuple[ReflowStyle, tuple[float, float, float]]:
    """Return the applied FOOTNOTE style and normalized renderer color."""
    return _resolved_reflow_style(resolved, expected_role=TypographyRole.FOOTNOTE, heading=False)


def _resolved_reflow_style(
    resolved: ResolvedParagraphStyle,
    *,
    expected_role: TypographyRole,
    heading: bool,
) -> tuple[ReflowStyle, tuple[float, float, float]]:
    if resolved.role is not expected_role:
        raise ValueError(
            f"{expected_role.value} reflow style requires a resolved "
            f"{expected_role.value.upper()} occurrence"
        )
    alignment = _ALIGNMENT.get(resolved.alignment)
    if alignment is None:
        raise ValueError(
            f"resolved {expected_role.value.upper()} alignment must be physical and known"
        )
    mixed = resolved.mixed_styles
    style = ReflowStyle(
        font_size=resolved.font_size_points,
        line_height=resolved.line_height_ratio,
        space_before=resolved.space_before_points,
        space_after=resolved.space_after_points,
        first_line_indent=resolved.first_line_indent_points,
        left_indent=resolved.left_indent_points,
        right_indent=resolved.right_indent_points,
        alignment=alignment,
        heading=heading,
        bold_requested=resolved.bold,
        bold_applied=False,
        italic_requested=resolved.italic,
        italic_applied=False,
        mixed_style=any(
            (
                mixed.mixed_font_family,
                mixed.mixed_font_size,
                mixed.mixed_weight,
                mixed.mixed_italic,
                mixed.mixed_color,
            )
        ),
        fallback_count=resolved.fallback_count,
    )
    color = resolved.color_rgb
    return style, (color.red / 255.0, color.green / 255.0, color.blue / 255.0)
