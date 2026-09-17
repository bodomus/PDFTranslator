"""Validate a ProjectWiki without network access or third-party dependencies."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

try:
    from .wiki_common import (
        FrontmatterError,
        WikiPage,
        default_wiki_root,
        discover_pages,
        markdown_link_targets,
        parse_page,
        resolve_local_target,
    )
except ImportError:  # Direct script execution.
    from wiki_common import (  # type: ignore[no-redef]
        FrontmatterError,
        WikiPage,
        default_wiki_root,
        discover_pages,
        markdown_link_targets,
        parse_page,
        resolve_local_target,
    )

REQUIRED_FIELDS = {"title", "type", "status", "created", "updated", "tags", "sources"}
ALLOWED_TYPES = {
    "architecture",
    "component",
    "workflow",
    "decision",
    "constraint",
    "failure-mode",
    "testing",
    "integration",
    "index",
    "log",
}
ALLOWED_STATUSES = {"active", "deprecated", "to-be-documented"}


@dataclass
class ValidationReport:
    """Concise, CI-oriented validation results."""

    pages: int = 0
    links: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_wiki(wiki_root: Path) -> ValidationReport:
    """Validate every Markdown file below *wiki_root*."""

    root = wiki_root.resolve()
    report = ValidationReport()
    if not root.is_dir():
        report.errors.append(f"wiki directory does not exist: {root}")
        return report

    parsed_pages: list[WikiPage] = []
    for path in discover_pages(root):
        report.pages += 1
        try:
            page = parse_page(path)
        except (OSError, UnicodeError, FrontmatterError) as error:
            report.errors.append(f"{_display(path, root)}: {error}")
            continue
        parsed_pages.append(page)
        _validate_metadata(page, root, report)
        _validate_markdown_links(page, root, report)

    if report.pages == 0:
        report.errors.append("wiki contains no Markdown pages")

    _validate_unique_titles(parsed_pages, root, report)
    return report


def _validate_metadata(page: WikiPage, root: Path, report: ValidationReport) -> None:
    label = _display(page.path, root)
    missing = sorted(REQUIRED_FIELDS - page.metadata.keys())
    if missing:
        report.errors.append(f"{label}: missing required fields: {', '.join(missing)}")

    title = page.scalar("title")
    if title is None or not title.strip():
        report.errors.append(f"{label}: title must be a non-empty scalar")

    page_type = page.scalar("type")
    if page_type not in ALLOWED_TYPES:
        report.errors.append(f"{label}: invalid type {page_type!r}")
    if page_type == "index" and page.path.name != "index.md":
        report.errors.append(f"{label}: type 'index' is only valid for index.md")
    if page_type == "log" and page.path.name != "log.md":
        report.errors.append(f"{label}: type 'log' is only valid for log.md")
    if page.path.name == "index.md" and page_type != "index":
        report.errors.append(f"{label}: index.md must use type 'index'")
    if page.path.name == "log.md" and page_type != "log":
        report.errors.append(f"{label}: log.md must use type 'log'")

    status = page.scalar("status")
    if status not in ALLOWED_STATUSES:
        report.errors.append(f"{label}: invalid status {status!r}")

    created = _validate_date(page, "created", label, report)
    updated = _validate_date(page, "updated", label, report)
    if created is not None and updated is not None and updated < created:
        report.errors.append(f"{label}: updated date is earlier than created date")

    for field_name in ("tags", "sources"):
        values = page.items(field_name)
        if values is None:
            report.errors.append(f"{label}: {field_name} must be a list")

    related = page.metadata.get("related")
    if related is not None and not isinstance(related, list):
        report.errors.append(f"{label}: related must be a list when present")

    for source in page.items("sources") or ():
        report.links += 1
        _validate_local_target(page.path, source, label, "source", report)


def _validate_date(
    page: WikiPage,
    field_name: str,
    label: str,
    report: ValidationReport,
) -> date | None:
    value = page.scalar(field_name)
    if value is None:
        if field_name in page.metadata:
            report.errors.append(f"{label}: {field_name} must be an ISO date scalar")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        report.errors.append(f"{label}: invalid {field_name} date {value!r}")
        return None


def _validate_markdown_links(page: WikiPage, root: Path, report: ValidationReport) -> None:
    label = _display(page.path, root)
    for target in markdown_link_targets(page.body):
        report.links += 1
        _validate_local_target(page.path, target, label, "link", report)


def _validate_local_target(
    page_path: Path,
    target: str,
    label: str,
    target_kind: str,
    report: ValidationReport,
) -> None:
    parsed = urlsplit(target.strip())
    if parsed.scheme or parsed.netloc or target.startswith("#"):
        return
    if Path(parsed.path).is_absolute():
        report.errors.append(f"{label}: {target_kind} must be relative: {target}")
        return
    resolved = resolve_local_target(page_path, target)
    if resolved is not None and not resolved.exists():
        report.errors.append(f"{label}: missing {target_kind} target: {target}")


def _validate_unique_titles(
    pages: list[WikiPage],
    root: Path,
    report: ValidationReport,
) -> None:
    seen: dict[str, Path] = {}
    for page in pages:
        title = page.scalar("title")
        if title is None or not title.strip():
            continue
        normalized = " ".join(title.split()).casefold()
        previous = seen.get(normalized)
        if previous is not None:
            report.errors.append(
                f"{_display(page.path, root)}: duplicate title {title!r}; "
                f"first used by {_display(previous, root)}"
            )
        else:
            seen[normalized] = page.path


def _display(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _print_report(report: ValidationReport) -> None:
    print("ProjectWiki validation")
    print(f"Pages: {report.pages}")
    print(f"Links: {report.links}")
    print(f"Errors: {len(report.errors)}")
    print(f"Warnings: {len(report.warnings)}")
    for error in report.errors:
        print(f"ERROR: {error}")
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    print("FAILED" if report.errors else "OK")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wiki",
        type=Path,
        default=default_wiki_root(),
        help="Wiki directory (default: repository knowledge/wiki)",
    )
    arguments = parser.parse_args(argv)
    report = validate_wiki(arguments.wiki)
    _print_report(report)
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
