"""Deterministic stage-aware checks for benchmark evidence."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from pdftranslate.benchmark.models import (
    BenchmarkFinding,
    BenchmarkSample,
    FindingStage,
    HumanReview,
)

_NUMBER = re.compile(r"(?<!\w)\d+(?:[.,]\d+)*(?:[-/–—]\d+)*(?!\w)")
_UNIT = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?\s?(?:%|mm|cm|m|km|mg|g|kg|ml|l|°C|°F)\b")
_URL = re.compile(r"https?://[^\s<>()]+")
_WINDOWS_PATH = re.compile(r"[A-Za-z]:\\(?:[^\\\s]+\\)*[^\\\s]+")
_OPTION = re.compile(r"(?<!\w)--[a-z0-9][a-z0-9-]*", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"_*__PDFTR_\d{4}__*_*")


def analyze_sample_output(
    sample: BenchmarkSample,
    source: str,
    output: str,
    *,
    source_segment_count: int,
    output_segment_count: int,
    segmentation_warning: bool = False,
    protection_error: str | None = None,
) -> tuple[BenchmarkFinding, ...]:
    """Check current model output without making semantic-quality claims."""
    findings: list[BenchmarkFinding] = []
    if source_segment_count != output_segment_count:
        findings.append(
            _finding(
                "segment-count-mismatch",
                "segmentation",
                "error",
                "Model output count does not match prepared source segment count.",
                (f"source={source_segment_count}", f"output={output_segment_count}"),
            )
        )
    if segmentation_warning:
        findings.append(
            _finding(
                "forced-segmentation",
                "segmentation",
                "warning",
                "Tokenizer limit forced a split outside preferred sentence boundaries.",
            )
        )
    if protection_error is not None:
        findings.append(
            _finding(
                "protected-token-restore-failed",
                "protected_token",
                "error",
                protection_error,
            )
        )
    findings.extend(_text_integrity_findings(sample, source, output, "model"))
    findings.extend(analyze_human_review(sample.human_review))
    return _deduplicate(findings)


def analyze_stage_trace(sample: BenchmarkSample) -> tuple[BenchmarkFinding, ...]:
    """Attribute optional historical snapshots to the boundary that changed text."""
    trace = sample.stage_trace
    if trace is None:
        return ()
    findings: list[BenchmarkFinding] = []
    extracted = trace.extracted_text if trace.extracted_text is not None else sample.source
    if extracted != sample.source:
        findings.append(
            _finding(
                "extracted-text-changed",
                "extraction",
                "error",
                "Extracted text differs from the benchmark source snapshot.",
            )
        )
        findings.extend(_text_integrity_findings(sample, sample.source, extracted, "extraction"))
    if (trace.source_segments or trace.translated_segments) and len(trace.source_segments) != len(
        trace.translated_segments
    ):
        findings.append(
            _finding(
                "observed-segment-count-mismatch",
                "segmentation",
                "error",
                "Observed translated segment count differs from source segment count.",
                (
                    f"source={len(trace.source_segments)}",
                    f"translated={len(trace.translated_segments)}",
                ),
            )
        )
    if trace.observed_translation is not None:
        findings.extend(
            _text_integrity_findings(sample, extracted, trace.observed_translation, "model")
        )
    if trace.rendered_text is not None and trace.rendered_text != trace.observed_translation:
        findings.append(
            _finding(
                "rendered-text-changed",
                "rendering",
                "error",
                "Rendered text differs from the translated-text snapshot.",
            )
        )
        assert trace.observed_translation is not None
        findings.extend(
            _text_integrity_findings(
                sample,
                trace.observed_translation,
                trace.rendered_text,
                "rendering",
            )
        )
    return tuple(
        finding.model_copy(update={"origin": "historical_trace"})
        for finding in _deduplicate(findings)
    )


def _text_integrity_findings(
    sample: BenchmarkSample,
    source: str,
    output: str,
    default_stage: FindingStage,
) -> list[BenchmarkFinding]:
    findings: list[BenchmarkFinding] = []
    protected_missing = [token for token in sample.protected_tokens if token not in output]
    if protected_missing:
        findings.append(
            _finding(
                "protected-token-damaged",
                "protected_token",
                "error",
                "One or more declared protected tokens are absent from output.",
                tuple(protected_missing),
            )
        )
    if _PLACEHOLDER.search(output):
        findings.append(
            _finding(
                "protected-placeholder-leaked",
                "protected_token",
                "error",
                "An internal protected-token placeholder leaked into output.",
            )
        )
    for code, pattern, label in (
        ("number-damaged", _NUMBER, "numbers or dates"),
        ("unit-damaged", _UNIT, "measurements or units"),
        ("url-damaged", _URL, "URLs"),
        ("path-damaged", _WINDOWS_PATH, "Windows paths"),
        ("option-damaged", _OPTION, "command options"),
    ):
        missing = _missing_values(pattern, source, output)
        if missing:
            findings.append(
                _finding(
                    code,
                    default_stage,
                    "error",
                    f"Output does not preserve all source {label}.",
                    missing,
                )
            )
    suspicious = tuple(char for char in output if _is_suspicious_character(char))
    if suspicious:
        findings.append(
            _finding(
                "suspicious-character",
                default_stage,
                "error",
                "Output contains replacement, noncharacter, or unexpected control characters.",
                tuple(f"U+{ord(char):04X}" for char in suspicious),
            )
        )
    source_normalized = " ".join(source.split()).casefold()
    output_normalized = " ".join(output.split()).casefold()
    if source_normalized and source_normalized == output_normalized:
        findings.append(
            _finding(
                "untranslated-output",
                default_stage,
                "error",
                "Output is identical to the English source after whitespace normalization.",
            )
        )
    if source_normalized and output_normalized:
        ratio = len(output_normalized) / len(source_normalized)
        if ratio < 0.25 or ratio > 4.0:
            findings.append(
                _finding(
                    "suspicious-length-ratio",
                    default_stage,
                    "warning",
                    "Output/source character length ratio is outside the conservative range.",
                    (f"ratio={ratio:.3f}",),
                )
            )
    return findings


def analyze_human_review(review: HumanReview | None) -> tuple[BenchmarkFinding, ...]:
    """Convert the current sample's explicit human scores into stage findings."""
    if review is None:
        return ()
    findings: list[BenchmarkFinding] = []
    for name, stage in (
        ("adequacy", "model"),
        ("fluency", "model"),
        ("terminology", "terminology"),
        ("token_preservation", "protected_token"),
        ("segmentation", "segmentation"),
        ("overall_acceptability", "model"),
    ):
        score = getattr(review, name)
        if score <= 2:
            findings.append(
                _finding(
                    f"human-{name.replace('_', '-')}",
                    stage,  # type: ignore[arg-type]
                    "error",
                    f"Human reviewer scored {name.replace('_', ' ')} {score}/5.",
                )
            )
    return tuple(findings)


def _missing_values(pattern: re.Pattern[str], source: str, output: str) -> tuple[str, ...]:
    source_values = Counter(match.group(0) for match in pattern.finditer(source))
    output_values = Counter(match.group(0) for match in pattern.finditer(output))
    missing: list[str] = []
    for value, count in source_values.items():
        missing.extend([value] * max(0, count - output_values[value]))
    return tuple(missing)


def _is_suspicious_character(char: str) -> bool:
    codepoint = ord(char)
    if char in {"\n", "\r", "\t"}:
        return False
    return (
        char == "\ufffd"
        or 0xFDD0 <= codepoint <= 0xFDEF
        or codepoint & 0xFFFF in {0xFFFE, 0xFFFF}
        or unicodedata.category(char) == "Cc"
    )


def _finding(
    code: str,
    stage: FindingStage,
    severity: str,
    message: str,
    evidence: tuple[str, ...] = (),
) -> BenchmarkFinding:
    return BenchmarkFinding(
        code=code,
        stage=stage,
        severity=severity,  # type: ignore[arg-type]
        message=message,
        evidence=evidence,
    )


def _deduplicate(findings: list[BenchmarkFinding]) -> tuple[BenchmarkFinding, ...]:
    unique: dict[tuple[str, str, tuple[str, ...]], BenchmarkFinding] = {}
    for finding in findings:
        unique[(finding.stage, finding.code, finding.evidence)] = finding
    return tuple(unique.values())
