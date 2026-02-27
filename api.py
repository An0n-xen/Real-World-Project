from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from medagent.config import configure_langsmith, get_settings
from medagent.logger import get_logger

logger = get_logger("medagent.api")

# ── Lifespan (startup) ───────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure LangSmith tracing before the app starts accepting requests."""
    configure_langsmith()
    yield


# ── App setup ────────────────────────────────────────────────────

app = FastAPI(
    title="MedAgent-Pro",
    description="Evidence-based multi-modal medical diagnosis API",
    version="0.1.0",
    lifespan=lifespan,
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
    from medagent.workflow import _normalize_disease_name

    settings = get_settings()
    diseases_dir = Path(settings.diseases_dir)
    diseases: list[dict] = []
    seen: set[str] = set()

    if diseases_dir.is_dir():
        for child in sorted(diseases_dir.iterdir()):
            if child.is_dir() and (child / "task.json").exists():
                task = _read_json(child / "task.json") or {}
                raw_disease = task.get("disease", child.name)
                norm_disease = _normalize_disease_name(raw_disease)
                
                if norm_disease not in seen:
                    seen.add(norm_disease)
                    diseases.append(
                        {
                            "name": child.name,
                            "disease": norm_disease,
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


from fastapi.responses import StreamingResponse

@app.post("/api/diagnose")
async def run_diagnose(
    disease: str = Form(...),
    patient_context: str = Form(""),
    image: UploadFile | None = File(None),
) -> StreamingResponse:
    """Run the diagnostic pipeline and stream real-time progress + results."""
    from medagent.workflow import run_diagnosis, _normalize_disease_name

    settings = get_settings()
    
    # Normalize "Diagnose potential glaucoma" -> "Glaucoma"
    disease_norm = _normalize_disease_name(disease)
    dir_name = disease_norm.lower().replace(" ", "_").replace("-", "_")
    disease_dir = os.path.join(settings.diseases_dir, dir_name)

    # Handle uploaded image
    image_path = ""
    if image and image.filename:
        images_dir = _PROJECT_ROOT / "images"
        images_dir.mkdir(exist_ok=True)
        image_path = str(images_dir / image.filename)
        content = await image.read()
        Path(image_path).write_bytes(content)

    async def _stream():
        q = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _progress(node_name: str):
            # Enqueue the progress event thread-safely
            msg = json.dumps({"type": "progress", "node": node_name}) + "\n"
            loop.call_soon_threadsafe(q.put_nowait, msg)

        # Start the pipeline thread
        task = asyncio.create_task(
            asyncio.to_thread(
                run_diagnosis,
                disease_dir,
                image_path,
                disease_name=disease,
                patient_context=patient_context,
                progress_cb=_progress,
            )
        )

        # Yield events as they arrive, with a heartbeat to prevent proxy timeouts
        while not task.done():
            try:
                # Wait up to 5 seconds for a new event
                msg = await asyncio.wait_for(q.get(), timeout=5.0)
                yield msg
            except asyncio.TimeoutError:
                # Keep-alive heartbeat (empty line) so Next.js doesn't close the stream
                yield "\n"

        # Flush any remaining events
        while not q.empty():
            yield q.get_nowait()

        # Send final result or error
        try:
            result = task.result()
            save_dir = result.get("save_dir", "")
            bundle: dict[str, Any] = {"diagnosis": result.get("diagnosis")}
            if save_dir:
                bundle.update(_load_result_bundle(save_dir))
            yield json.dumps({"type": "result", "data": bundle}) + "\n"
        except Exception as exc:
            logger.exception("Diagnosis pipeline failed")
            yield json.dumps({"type": "error", "error": str(exc)}) + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


# ── Static files & SPA fallback ──────────────────────────────────

if _FRONTEND_DIR.is_dir():
    # Mount Next.js _next folder
    _next_dir = _FRONTEND_DIR / "_next"
    if _next_dir.is_dir():
        app.mount("/_next", StaticFiles(directory=str(_next_dir)), name="_next")
    
    # Optional: also mount raw frontend dir if needed
    app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="static")

@app.get("/")
async def serve_frontend() -> FileResponse:
    return FileResponse(str(_FRONTEND_DIR / "index.html"))
