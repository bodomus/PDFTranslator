"""Document-level repeated header, footer and boilerplate detection."""

from pdftranslate.repeated.classifier import classify_repeated_elements
from pdftranslate.repeated.models import (
    RepeatedBlockClassification,
    RepeatedElementAnalysis,
    RepeatedElementGroup,
    RepeatedElementKind,
    RepeatedElementMetrics,
    RepeatedElementOptions,
    RepeatedElementPolicy,
    RepeatedElementsMode,
)

__all__ = [
    "RepeatedBlockClassification",
    "RepeatedElementAnalysis",
    "RepeatedElementGroup",
    "RepeatedElementKind",
    "RepeatedElementMetrics",
    "RepeatedElementOptions",
    "RepeatedElementPolicy",
    "RepeatedElementsMode",
    "classify_repeated_elements",
]
