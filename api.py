from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from medagent.config import get_settings
from medagent.logger import get_logger

logger = get_logger("medagent.api")

# ── App setup ────────────────────────────────────────────────────

app = FastAPI(
    title="MedAgent-Pro",
    description="Evidence-based multi-modal medical diagnosis API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_PROJECT_ROOT = Path(__file__).resolve().parent
_FRONTEND_DIR = _PROJECT_ROOT / "frontend"


# ── Helpers ──────────────────────────────────────────────────────


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


# ── API Routes ───────────────────────────────────────────────────


@app.get("/api/diseases")
async def list_diseases() -> JSONResponse:
    """Return every disease directory that already has a task.json."""
    settings = get_settings()
    diseases_dir = Path(settings.diseases_dir)
    diseases: list[dict] = []

    if diseases_dir.is_dir():
        for child in sorted(diseases_dir.iterdir()):
            if child.is_dir() and (child / "task.json").exists():
                task = _read_json(child / "task.json") or {}
                diseases.append(
                    {
                        "name": child.name,
                        "disease": task.get("disease", child.name),
                        "input": task.get("input", ""),
                    }
                )

    return JSONResponse(diseases)


@app.get("/api/results")
async def list_results() -> JSONResponse:
    """List all past diagnosis records grouped by disease."""
    settings = get_settings()
    output_dir = Path(settings.output_dir)
    results: list[dict] = []

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

    return JSONResponse(results)


@app.get("/api/results/{disease}/{record}")
async def get_result(disease: str, record: str) -> JSONResponse:
    """Return the full result bundle for a specific record."""
    settings = get_settings()
    record_dir = Path(settings.output_dir) / disease / "record" / record
    if not record_dir.is_dir():
        return JSONResponse({"error": "Record not found"}, status_code=404)

    bundle = _load_result_bundle(record_dir)
    return JSONResponse(bundle)


@app.post("/api/diagnose")
async def run_diagnose(
    disease: str = Form(...),
    patient_context: str = Form(""),
    image: UploadFile | None = File(None),
) -> JSONResponse:
    """Run the full diagnostic pipeline and return results + trace."""
    from medagent.workflow import run_diagnosis

    settings = get_settings()
    dir_name = disease.lower().replace(" ", "_").replace("-", "_")
    disease_dir = os.path.join(settings.diseases_dir, dir_name)

    # Handle uploaded image
    image_path = ""
    if image and image.filename:
        images_dir = _PROJECT_ROOT / "images"
        images_dir.mkdir(exist_ok=True)
        image_path = str(images_dir / image.filename)
        content = await image.read()
        Path(image_path).write_bytes(content)

    # Run pipeline in a thread to avoid blocking the event loop
    try:
        result = await asyncio.to_thread(
            run_diagnosis,
            disease_dir,
            image_path,
            disease_name=disease,
            patient_context=patient_context,
        )
    except Exception as exc:
        logger.exception("Diagnosis pipeline failed")
        return JSONResponse({"error": str(exc)}, status_code=500)

    # Build the response bundle from saved files
    save_dir = result.get("save_dir", "")
    bundle: dict[str, Any] = {"diagnosis": result.get("diagnosis")}
    if save_dir:
        bundle.update(_load_result_bundle(save_dir))

    return JSONResponse(bundle)


# ── Static files & SPA fallback ──────────────────────────────────

if _FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_frontend() -> FileResponse:
    return FileResponse(str(_FRONTEND_DIR / "index.html"))
