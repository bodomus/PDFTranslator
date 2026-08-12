"""Actionable glossary loading and compliance failures."""

from __future__ import annotations


class GlossaryError(ValueError):
    def __init__(self, message: str, *, code: str = "GLOSSARY_CONFLICT") -> None:
        super().__init__(message)
        self.code = code


class GlossaryComplianceError(GlossaryError):
    pass
