"""Text block and typography models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainModel(BaseModel):
    """Strict immutable base for JSON-safe domain values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class BoundingBox(DomainModel):
    """Rectangle in PyMuPDF's effective PDF page coordinate system."""

    x0: float
    y0: float
    x1: float
    y1: float

    @model_validator(mode="after")
    def validate_extents(self) -> BoundingBox:
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError("bounding box maximums must not be less than minimums")
        return self

    @property
    def area(self) -> float:
        return max(0.0, self.x1 - self.x0) * max(0.0, self.y1 - self.y0)


class TextSpan(DomainModel):
    """A same-style text run within a block."""

    text: str
    bbox: BoundingBox
    font_name: str | None = None
    font_size: float | None = Field(default=None, ge=0)
    text_color: int | None = Field(default=None, ge=0)
    bold: bool | None = None
    italic: bool | None = None


class TextBlock(DomainModel):
    """A PyMuPDF text block retained without cross-column merging."""

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    bbox: BoundingBox
    original_order: int = Field(ge=0)
    normalized_order: int = Field(ge=0)
    spans: tuple[TextSpan, ...] = ()
