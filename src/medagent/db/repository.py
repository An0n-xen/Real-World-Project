from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from medagent.config import get_settings
from medagent.logger import get_logger

logger = get_logger(__name__)


# ── Helpers (file-mode) ──────────────────────────────────────────


def _read_json(path: str | Path) -> dict | list | None:
    """Read a JSON file, returning *None* on any failure."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return None


def _load_result_bundle(record_dir: str | Path) -> dict[str, Any]:
    """Load all saved JSON artefacts from a record directory."""
    d = Path(record_dir)
    return {
        "pipeline_trace": _read_json(d / "pipeline_trace.json"),
        "final_diagnosis": _read_json(d / "final_diagnosis.json"),
        "reasoning_trace": _read_json(d / "reasoning_trace.json"),
        "concepts": _read_json(d / "concepts.json"),
        "brief_diagnosis": _read_json(d / "brief_diagnosis.json"),
    }


# ── Public API ───────────────────────────────────────────────────


async def list_all_records() -> list[dict[str, Any]]:
    """Return a list of all diagnosis record summaries."""
    settings = get_settings()

    if settings.mongodb_enabled:
        from medagent.db.models import DiagnosisRecord

        records = await DiagnosisRecord.find_all().to_list()
        return [
            {
                "disease": r.disease,
                "record": r.record_id,
                "has_trace": r.has_trace,
                "start_time": r.start_time,
                "patient_context": r.patient_context,
            }
            for r in records
        ]

    # File mode — scan output directories
    output_dir = Path(settings.output_dir)
    results: list[dict[str, Any]] = []

    if output_dir.is_dir():
        for disease_dir in sorted(output_dir.iterdir()):
            if not disease_dir.is_dir() or disease_dir.name.startswith("."):
                continue
            record_root = disease_dir / "record"
            if not record_root.is_dir():
                continue
            for record in sorted(record_root.iterdir()):
                if not record.is_dir():
                    continue
                trace = _read_json(record / "pipeline_trace.json")
                results.append(
                    {
                        "disease": disease_dir.name,
                        "record": record.name,
                        "has_trace": trace is not None,
                        "start_time": (trace or {}).get("start_time", ""),
                        "patient_context": (trace or {}).get("patient_context", ""),
                    }
                )

    return results


async def get_record_bundle(disease: str, record_id: str) -> dict[str, Any] | None:
    """Return the full result bundle for one record, or *None* if missing."""
    settings = get_settings()

    if settings.mongodb_enabled:
        from medagent.db.models import DiagnosisRecord

        rec = await DiagnosisRecord.find_one(
            DiagnosisRecord.disease == disease,
            DiagnosisRecord.record_id == record_id,
        )
        if rec is None:
            return None
        return {
            "pipeline_trace": rec.pipeline_trace,
            "final_diagnosis": rec.final_diagnosis,
            "reasoning_trace": rec.reasoning_trace,
            "concepts": rec.concepts,
            "brief_diagnosis": rec.brief_diagnosis,
        }

    # File mode
    record_dir = Path(settings.output_dir) / disease / "record" / record_id
    if not record_dir.is_dir():
        return None
    return _load_result_bundle(record_dir)


async def save_record(
    disease: str,
    record_id: str,
    bundle: dict[str, Any],
    patient_context: str = "",
    save_dir: str = "",
) -> None:
    """Persist a diagnosis record to MongoDB or disk.

    *bundle* should contain keys: pipeline_trace, final_diagnosis,
    reasoning_trace, concepts, brief_diagnosis.
    """
    settings = get_settings()

    if settings.mongodb_enabled:
        from medagent.db.models import DiagnosisRecord

        pipeline_trace = bundle.get("pipeline_trace")
        has_trace = pipeline_trace is not None
        start_time = ""
        if isinstance(pipeline_trace, dict):
            start_time = pipeline_trace.get("start_time", "")

        existing = await DiagnosisRecord.find_one(
            DiagnosisRecord.disease == disease,
            DiagnosisRecord.record_id == record_id,
        )
        if existing:
            existing.pipeline_trace = pipeline_trace
            existing.final_diagnosis = bundle.get("final_diagnosis")
            existing.reasoning_trace = bundle.get("reasoning_trace")
            existing.concepts = bundle.get("concepts")
            existing.brief_diagnosis = bundle.get("brief_diagnosis")
            existing.has_trace = has_trace
            existing.start_time = start_time
            existing.patient_context = patient_context
            await existing.save()
        else:
            rec = DiagnosisRecord(
                disease=disease,
                record_id=record_id,
                pipeline_trace=pipeline_trace,
                final_diagnosis=bundle.get("final_diagnosis"),
                reasoning_trace=bundle.get("reasoning_trace"),
                concepts=bundle.get("concepts"),
                brief_diagnosis=bundle.get("brief_diagnosis"),
                has_trace=has_trace,
                start_time=start_time,
                patient_context=patient_context,
            )
            await rec.insert()

        logger.info("Record saved to MongoDB  disease=%s  record=%s", disease, record_id)
        return

    # File mode — write JSON files to disk
    if not save_dir:
        save_dir = str(Path(settings.output_dir) / disease / "record" / record_id)

    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    for filename, key in [
        ("pipeline_trace.json", "pipeline_trace"),
        ("final_diagnosis.json", "final_diagnosis"),
        ("reasoning_trace.json", "reasoning_trace"),
        ("concepts.json", "concepts"),
        ("brief_diagnosis.json", "brief_diagnosis"),
    ]:
        data = bundle.get(key)
        if data is not None:
            (save_path / filename).write_text(
                json.dumps(data, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )

    logger.info("Record saved to disk  dir=%s", save_dir)
