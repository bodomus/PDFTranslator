"""Persistent resumable workspace with atomic manifests and retained diagnostics."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pdftranslate.domain.document import ExtractedDocument, InspectionReport, SourceDocument
from pdftranslate.pipeline.errors import PipelineStateError
from pdftranslate.pipeline.models import PipelineOptions, PipelineStage
from pdftranslate.serialization import read_document_json, write_document_json

OptionValue = str | int | float | bool | None
StageStatus = Literal["pending", "completed", "failed", "interrupted"]


def _now() -> datetime:
    return datetime.now(UTC)


class StageRecord(BaseModel):
    """Persisted state for one deterministic stage."""

    model_config = ConfigDict(extra="forbid")

    status: StageStatus = "pending"
    artifact: str | None = None
    updated_at: datetime = Field(default_factory=_now)


class PipelineManifest(BaseModel):
    """Versioned identity and lifecycle for a resumable run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: SourceDocument
    options: dict[str, OptionValue]
    stages: dict[str, StageRecord]
    created_at: datetime
    updated_at: datetime


class PipelineWorkspace:
    """Own all artifacts for one source/options identity below the app cache."""

    def __init__(self, path: Path, manifest: PipelineManifest) -> None:
        self.path = path
        self.manifest = manifest
        self.manifest_path = path / "manifest.json"
        self.inspection_path = path / "inspection.json"
        self.extracted_path = path / "extracted.json"
        self.translated_path = path / "translated.json"
        self.rendered_path = path / "rendered.pdf"
        self.log_path = path / "pipeline.log"
        self.failure_path = path / "failure.json"

    @classmethod
    def prepare(
        cls,
        cache_root: Path,
        source: SourceDocument,
        options: PipelineOptions,
    ) -> PipelineWorkspace:
        identity_options = options.identity_values()
        run_id = _run_identity(source, identity_options)
        path = cache_root.expanduser().resolve() / "workspaces" / run_id
        manifest_path = path / "manifest.json"

        if options.resume:
            if not manifest_path.is_file():
                raise PipelineStateError(
                    "no compatible pipeline state exists for this source and option set"
                )
            manifest = _read_manifest(manifest_path)
            if (
                manifest.run_id != run_id
                or manifest.source != source
                or manifest.options != identity_options
            ):
                raise PipelineStateError("pipeline state is incompatible with this run")
            return cls(path, manifest)

        path.mkdir(parents=True, exist_ok=True)
        now = _now()
        manifest = PipelineManifest(
            run_id=run_id,
            source=source,
            options=identity_options,
            stages={stage.value: StageRecord() for stage in PipelineStage},
            created_at=now,
            updated_at=now,
        )
        workspace = cls(path, manifest)
        workspace._save_manifest()
        workspace.log("pipeline initialized")
        return workspace

    @property
    def run_id(self) -> str:
        return self.manifest.run_id

    def stage_artifact(self, stage: PipelineStage) -> Path:
        paths = {
            PipelineStage.INSPECT: self.inspection_path,
            PipelineStage.EXTRACT: self.extracted_path,
            PipelineStage.TRANSLATE: self.translated_path,
            PipelineStage.RENDER: self.rendered_path,
            PipelineStage.VALIDATE: Path(str(self.manifest.options["output_path"])),
        }
        return paths[stage]

    def can_reuse(self, stage: PipelineStage) -> bool:
        record = self.manifest.stages[stage.value]
        if record.status != "completed" or record.artifact is None:
            return False
        return Path(record.artifact).is_file()

    def mark_completed(self, stage: PipelineStage, artifact: Path) -> None:
        now = _now()
        self.manifest.stages[stage.value] = StageRecord(
            status="completed",
            artifact=str(artifact.resolve()),
            updated_at=now,
        )
        self.manifest.updated_at = now
        self._save_manifest()
        self.log(f"stage {stage.value} completed: {artifact.resolve()}")

    def write_inspection(self, report: InspectionReport) -> None:
        _write_text_atomic(self.inspection_path, report.model_dump_json(indent=2) + "\n")

    def read_inspection(self) -> InspectionReport:
        try:
            return InspectionReport.model_validate_json(
                self.inspection_path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as error:
            raise PipelineStateError(f"invalid inspection artifact: {error}") from error

    def write_document(self, document: ExtractedDocument, path: Path) -> None:
        write_document_json(document, path, overwrite=True)

    def read_document(self, path: Path) -> ExtractedDocument:
        return read_document_json(path)

    def record_failure(
        self,
        stage: PipelineStage,
        message: str,
        *,
        interrupted: bool,
        details: str,
    ) -> None:
        now = _now()
        self.manifest.stages[stage.value] = StageRecord(
            status="interrupted" if interrupted else "failed",
            artifact=(
                str(self.stage_artifact(stage).resolve())
                if self.stage_artifact(stage).exists()
                else None
            ),
            updated_at=now,
        )
        self.manifest.updated_at = now
        self._save_manifest()
        failure = {
            "stage": stage.value,
            "interrupted": interrupted,
            "message": message,
            "occurred_at": now.isoformat(),
            "log_path": str(self.log_path.resolve()),
        }
        _write_text_atomic(
            self.failure_path,
            json.dumps(failure, ensure_ascii=False, indent=2) + "\n",
        )
        self.log(f"stage {stage.value} failed: {message}\n{details}")

    def log(self, message: str) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        timestamp = _now().isoformat()
        with self.log_path.open("a", encoding="utf-8", newline="\n") as log_file:
            for line in message.splitlines() or [""]:
                log_file.write(f"{timestamp} {line}\n")

    def _save_manifest(self) -> None:
        payload = self.manifest.model_dump_json(indent=2) + "\n"
        _write_text_atomic(self.manifest_path, payload)


def _run_identity(source: SourceDocument, options: dict[str, OptionValue]) -> str:
    payload = {
        "source": source.model_dump(mode="json"),
        "options": options,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_manifest(path: Path) -> PipelineManifest:
    try:
        return PipelineManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise PipelineStateError(f"invalid pipeline manifest: {error}") from error


def _write_text_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
