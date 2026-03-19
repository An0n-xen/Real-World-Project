from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from beanie import Document, Indexed
from pydantic import Field


class DiagnosisRecord(Document):
    """A single diagnosis record stored in MongoDB."""

    disease: str
    record_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pipeline_trace: dict[str, Any] | None = None
    final_diagnosis: dict[str, Any] | None = None
    reasoning_trace: dict[str, Any] | None = None
    concepts: dict[str, Any] | None = None
    brief_diagnosis: dict[str, Any] | None = None
    has_trace: bool = False
    start_time: str = ""
    patient_context: str = ""

    class Settings:
        name = "diagnosis_records"
        indexes = [
            [("disease", 1), ("record_id", 1)],
        ]
