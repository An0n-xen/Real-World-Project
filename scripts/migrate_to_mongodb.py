"""One-shot migration: import existing file-based diagnosis records into MongoDB.

Usage:
    uv run python scripts/migrate_to_mongodb.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from medagent.config import get_settings
from medagent.db.connection import init_db, close_db
from medagent.db.models import DiagnosisRecord


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return None


async def migrate() -> None:
    settings = get_settings()

    if not settings.mongodb_url:
        print("ERROR: MONGODB_URL is not set in .env")
        sys.exit(1)

    # Force enable for migration
    settings.mongodb_enabled = True
    await init_db()

    output_dir = Path(settings.output_dir)
    if not output_dir.is_dir():
        print(f"No output directory found at {output_dir}")
        await close_db()
        return

    migrated = 0
    skipped = 0

    for disease_dir in sorted(output_dir.iterdir()):
        if not disease_dir.is_dir() or disease_dir.name.startswith("."):
            continue
        record_root = disease_dir / "record"
        if not record_root.is_dir():
            continue

        for record_dir in sorted(record_root.iterdir()):
            if not record_dir.is_dir():
                continue

            disease = disease_dir.name
            record_id = record_dir.name

            # Check if already exists
            existing = await DiagnosisRecord.find_one(
                DiagnosisRecord.disease == disease,
                DiagnosisRecord.record_id == record_id,
            )
            if existing:
                print(f"  SKIP  {disease}/{record_id} (already exists)")
                skipped += 1
                continue

            pipeline_trace = _read_json(record_dir / "pipeline_trace.json")
            final_diagnosis = _read_json(record_dir / "final_diagnosis.json")
            reasoning_trace = _read_json(record_dir / "reasoning_trace.json")
            concepts = _read_json(record_dir / "concepts.json")
            brief_diagnosis = _read_json(record_dir / "brief_diagnosis.json")

            has_trace = pipeline_trace is not None
            start_time = ""
            patient_context = ""
            if isinstance(pipeline_trace, dict):
                start_time = pipeline_trace.get("start_time", "")
                patient_context = pipeline_trace.get("patient_context", "")

            rec = DiagnosisRecord(
                disease=disease,
                record_id=record_id,
                pipeline_trace=pipeline_trace,
                final_diagnosis=final_diagnosis,
                reasoning_trace=reasoning_trace,
                concepts=concepts,
                brief_diagnosis=brief_diagnosis,
                has_trace=has_trace,
                start_time=start_time,
                patient_context=patient_context,
            )
            await rec.insert()
            print(f"  OK    {disease}/{record_id}")
            migrated += 1

    await close_db()
    print(f"\nDone. Migrated: {migrated}, Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(migrate())
