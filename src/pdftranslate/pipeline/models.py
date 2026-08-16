"""Typed pipeline contracts independent from Typer and third-party adapters."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pdftranslate.domain.document import InspectionReport, TranslationStatistics
from pdftranslate.glossary import GLOSSARY_BEHAVIOR_REVISION, LoadedGlossary
from pdftranslate.glossary.models import GlossaryTranslationEvidence
from pdftranslate.translation.cache import TRANSLATION_BEHAVIOR_REVISION

DeviceRequest = Literal["auto", "cpu", "cuda"]
OcrMode = Literal["auto", "on", "off"]
ReportFormat = Literal["json", "html", "both"]
PIPELINE_BEHAVIOR_REVISION = 5


class PipelineStage(StrEnum):
    """Stable ordered pipeline stage names persisted in manifests."""

    INSPECT = "inspect"
    OCR = "ocr"
    EXTRACT = "extract"
    TRANSLATE = "translate"
    RENDER = "render"
    VALIDATE = "validate"


STAGE_LABELS: dict[PipelineStage, str] = {
    PipelineStage.INSPECT: "Inspect",
    PipelineStage.OCR: "OCR",
    PipelineStage.EXTRACT: "Extract",
    PipelineStage.TRANSLATE: "Translate",
    PipelineStage.RENDER: "Render",
    PipelineStage.VALIDATE: "Validate",
}


@dataclass(frozen=True)
class PipelineOptions:
    """All behavior-affecting settings for one end-to-end run."""

    input_path: Path
    output_path: Path
    pages: str | None = None
    paragraph_reconstruction: Literal["conservative", "off"] = "conservative"
    repeated_elements: Literal["auto", "off"] = "auto"
    backend: str = "nllb"
    model: str = "facebook/nllb-200-distilled-600M"
    device: DeviceRequest = "auto"
    batch_size: int = 8
    max_input_tokens: int = 512
    cache_dir: Path | None = None
    glossary_path: Path | None = None
    glossary_fingerprint: str | None = None
    glossary_schema_version: str | None = None
    glossary_version: str | None = None
    glossary_behavior_revision: int | None = None
    offline: bool = False
    resume: bool = False
    overwrite: bool = False
    font_path: Path | None = None
    min_font_size: float = 6.0
    font_size_step: float = 0.5
    line_height: float = 1.2
    redaction_padding: float = 0.5
    allow_expand: bool = False
    ocr: OcrMode = "auto"
    ocr_language: str = "eng"
    ocr_deskew: bool = False
    ocr_clean: bool = False
    ocr_rotate_pages: bool = False
    ocr_force: bool = False
    report: bool = False
    report_format: ReportFormat = "both"
    report_dir: Path | None = None
    debug_layout: bool = False
    include_report_text: bool = False

    def __post_init__(self) -> None:
        if self.paragraph_reconstruction not in {"conservative", "off"}:
            raise ValueError("paragraph reconstruction must be conservative or off")
        if self.repeated_elements not in {"auto", "off"}:
            raise ValueError("repeated elements must be auto or off")
        if self.backend != "nllb":
            raise ValueError(f"unsupported translation backend: {self.backend}")
        if self.device not in {"auto", "cpu", "cuda"}:
            raise ValueError("device must be one of: auto, cpu, cuda")
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if self.max_input_tokens < 8:
            raise ValueError("max_input_tokens must be at least 8")
        if self.min_font_size <= 0 or self.font_size_step <= 0 or self.line_height <= 0:
            raise ValueError("font and line-size options must be greater than zero")
        if self.redaction_padding < 0:
            raise ValueError("redaction_padding cannot be negative")
        if self.resume and self.overwrite:
            raise ValueError("--resume and --overwrite cannot be used together")

        if self.ocr not in {"auto", "on", "off"}:
            raise ValueError("ocr mode must be one of: auto, on, off")
        if not self.ocr_language.strip():
            raise ValueError("OCR language cannot be empty")
        processing_requested = (
            self.ocr_deskew or self.ocr_clean or self.ocr_rotate_pages or self.ocr_force
        )
        if self.ocr == "off" and processing_requested:
            raise ValueError("OCR processing options cannot be used with --ocr off")
        if self.ocr_force and self.ocr != "on":
            raise ValueError("--ocr-force requires --ocr on")
        if self.report_format not in {"json", "html", "both"}:
            raise ValueError("report format must be one of: json, html, both")
        if self.include_report_text and not self.report:
            raise ValueError("--include-report-text requires --report")

        if self.glossary_path is None and self.glossary_fingerprint is not None:
            raise ValueError("glossary identity requires a glossary path")

    def with_glossary(self, glossary: LoadedGlossary | None) -> PipelineOptions:
        """Attach validated semantic identity without relying on path or mtime."""
        if glossary is None:
            return self
        return replace(
            self,
            glossary_fingerprint=glossary.fingerprint,
            glossary_schema_version=glossary.document.schema_version,
            glossary_version=glossary.document.glossary_version,
            glossary_behavior_revision=GLOSSARY_BEHAVIOR_REVISION,
        )

    def identity_values(self) -> dict[str, str | int | float | bool | None]:
        """Return canonical values that determine artifact compatibility."""
        font = self.font_path.expanduser().resolve() if self.font_path is not None else None
        return {
            "pipeline_behavior_revision": PIPELINE_BEHAVIOR_REVISION,
            "translation_behavior_revision": TRANSLATION_BEHAVIOR_REVISION,
            "output_path": str(self.output_path.expanduser().resolve()),
            "pages": self.pages,
            "paragraph_reconstruction": self.paragraph_reconstruction,
            "repeated_elements": self.repeated_elements,
            "backend": self.backend,
            "model": self.model,
            "device": self.device,
            "batch_size": self.batch_size,
            "max_input_tokens": self.max_input_tokens,
            "offline": self.offline,
            "font_path": str(font) if font is not None else None,
            "min_font_size": self.min_font_size,
            "glossary_fingerprint": self.glossary_fingerprint,
            "glossary_schema_version": self.glossary_schema_version,
            "glossary_version": self.glossary_version,
            "glossary_behavior_revision": self.glossary_behavior_revision,
            "glossary_languages": "en-ru" if self.glossary_fingerprint else None,
            "font_size_step": self.font_size_step,
            "line_height": self.line_height,
            "redaction_padding": self.redaction_padding,
            "allow_expand": self.allow_expand,
            "ocr": self.ocr,
            "ocr_language": self.ocr_language,
            "ocr_deskew": self.ocr_deskew,
            "ocr_clean": self.ocr_clean,
            "ocr_rotate_pages": self.ocr_rotate_pages,
            "ocr_force": self.ocr_force,
        }


@dataclass(frozen=True)
class StageProgress:
    """One stage transition suitable for terminal and log reporting."""

    index: int
    total: int
    stage: PipelineStage
    reused: bool = False


@dataclass(frozen=True)
class PipelineResult:
    """Summary of a successfully validated and published run."""

    output_path: Path
    workspace_path: Path
    run_id: str
    reused_stages: tuple[PipelineStage, ...]
    statistics: TranslationStatistics
    file_size: int
    ocr_status: Literal["skipped", "processed", "reused"]
    ocr_pages: tuple[int, ...] = ()
    ocr_warnings: tuple[str, ...] = ()
    pages_processed: int = 0
    report_paths: tuple[Path, ...] = ()
    debug_layout_path: Path | None = None
    glossary: GlossaryTranslationEvidence | None = None


@dataclass(frozen=True)
class DryRunResult:
    """Inspection-only planning result that never constructs a model backend."""

    inspection: InspectionReport
    selected_pages: tuple[int, ...]
    selected_page_classifications: tuple[str, ...]
    estimated_text_blocks: int
    ocr_required: bool
    ocr_will_run: bool
    ocr_pages: tuple[int, ...]
    backend: str
    device: DeviceRequest
    output_path: Path
    expected_stages: tuple[PipelineStage, ...] = tuple(PipelineStage)


def default_output_path(input_path: Path) -> Path:
    """Return the documented sibling `<stem>.ru.pdf` output path."""
    source = input_path.expanduser()
    return source.with_name(f"{source.stem}.ru.pdf")
