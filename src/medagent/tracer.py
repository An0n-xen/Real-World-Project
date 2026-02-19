from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from medagent.logger import get_logger

logger = get_logger(__name__)


# ── Schemas ──────────────────────────────────────────────────────


class NodeTrace(BaseModel):
    """Trace record for a single workflow node."""

    node_name: str
    status: str = "pending"          # pending | running | completed | error
    start_time: str = ""
    end_time: str = ""
    duration_seconds: float = 0.0
    inputs_summary: dict[str, Any] = Field(default_factory=dict)
    outputs_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class PipelineTrace(BaseModel):
    """Full trace of a pipeline execution."""

    pipeline_name: str = "MedAgent-Pro"
    disease: str = ""
    image_path: str = ""
    patient_context: str = ""
    start_time: str = ""
    end_time: str = ""
    total_duration_seconds: float = 0.0
    nodes: list[NodeTrace] = Field(default_factory=list)
    final_diagnosis: dict[str, Any] = Field(default_factory=dict)


# ── Tracer ───────────────────────────────────────────────────────


class PipelineTracer:
    """Records execution traces for each workflow node.

    Usage::

        tracer = PipelineTracer(disease="glaucoma")
        tracer.start_node("load_config", inputs={"disease_dir": "..."})
        # ... node work ...
        tracer.end_node("load_config", outputs={"tools": 4})
        tracer.save(save_dir)
    """

    def __init__(self, disease: str = "", image_path: str = "", patient_context: str = ""):
        self._trace = PipelineTrace(
            disease=disease,
            image_path=image_path,
            patient_context=patient_context[:200] if patient_context else "",
            start_time=_now(),
        )
        self._active: dict[str, float] = {}      # node_name → start timestamp
        self._node_map: dict[str, NodeTrace] = {}  # node_name → NodeTrace

    # ── Recording ────────────────────────────────────────────────

    def start_node(
        self,
        node_name: str,
        inputs: dict[str, Any] | None = None,
    ) -> None:
        """Mark a node as started."""
        node = NodeTrace(
            node_name=node_name,
            status="running",
            start_time=_now(),
            inputs_summary=_summarize(inputs or {}),
        )
        self._trace.nodes.append(node)
        self._node_map[node_name] = node
        self._active[node_name] = time.perf_counter()
        logger.debug("TRACE ▶ %s started", node_name)

    def end_node(
        self,
        node_name: str,
        outputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        """Mark a node as completed (or errored)."""
        node = self._node_map.get(node_name)
        if node is None:
            logger.warning("TRACE end_node called for unknown node '%s'", node_name)
            return

        elapsed = time.perf_counter() - self._active.pop(node_name, time.perf_counter())
        node.status = "error" if error else "completed"
        node.end_time = _now()
        node.duration_seconds = round(elapsed, 3)
        node.outputs_summary = _summarize(outputs or {})
        node.metadata = metadata or {}
        node.error = error

        logger.debug(
            "TRACE ■ %s %s (%.2fs)",
            node_name, node.status, elapsed,
        )

    def set_final_diagnosis(self, diagnosis: dict[str, Any]) -> None:
        """Record the final diagnosis in the trace."""
        self._trace.final_diagnosis = _summarize(diagnosis)

    def finalize(self) -> PipelineTrace:
        """Close the trace and return it."""
        self._trace.end_time = _now()
        start = self._trace.start_time
        if start:
            try:
                t0 = datetime.fromisoformat(start)
                t1 = datetime.fromisoformat(self._trace.end_time)
                self._trace.total_duration_seconds = round((t1 - t0).total_seconds(), 3)
            except (ValueError, TypeError):
                pass
        return self._trace

    # ── Persistence ──────────────────────────────────────────────

    def save_trace(self, save_dir: str) -> str:
        """Save ``pipeline_trace.json`` and return its path."""
        trace = self.finalize()
        path = Path(save_dir) / "pipeline_trace.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(trace.model_dump(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        logger.info("Pipeline trace saved → %s", path)
        return str(path)

    def generate_report(self, save_dir: str) -> str:
        """Generate a human-readable ``diagnosis_report.md`` and return its path."""
        trace = self.finalize()
        lines: list[str] = []

        lines.append(f"# Diagnostic Report: {trace.disease}")
        lines.append("")
        lines.append(f"**Date:** {trace.start_time}")
        lines.append(f"**Image:** `{trace.image_path}`")
        if trace.patient_context:
            lines.append(f"**Patient Context:** {trace.patient_context}")
        lines.append(f"**Total Duration:** {trace.total_duration_seconds}s")
        lines.append("")

        # Pipeline steps
        lines.append("## Pipeline Execution")
        lines.append("")
        lines.append("| Step | Node | Status | Duration |")
        lines.append("|------|------|--------|----------|")
        for i, node in enumerate(trace.nodes, 1):
            status_icon = "✅" if node.status == "completed" else "❌" if node.status == "error" else "⏳"
            lines.append(
                f"| {i} | {node.node_name} | {status_icon} {node.status} | {node.duration_seconds}s |"
            )
        lines.append("")

        # Node details
        lines.append("## Step Details")
        lines.append("")
        for node in trace.nodes:
            lines.append(f"### {node.node_name}")
            if node.inputs_summary:
                lines.append(f"- **Inputs:** {_format_dict(node.inputs_summary)}")
            if node.outputs_summary:
                lines.append(f"- **Outputs:** {_format_dict(node.outputs_summary)}")
            if node.metadata:
                lines.append(f"- **Metadata:** {_format_dict(node.metadata)}")
            if node.error:
                lines.append(f"- **Error:** {node.error}")
            lines.append("")

        # Final diagnosis
        if trace.final_diagnosis:
            lines.append("## Final Diagnosis")
            lines.append("")
            diag = trace.final_diagnosis
            lines.append(f"- **Diagnosis:** {diag.get('diagnosis', 'N/A')}")
            lines.append(f"- **Confidence:** {diag.get('confidence', 'N/A')}")
            lines.append(f"- **Weighted Score:** {diag.get('weighted_score', 'N/A')}")
            lines.append(f"- **Threshold:** {diag.get('threshold', 'N/A')}")
            if diag.get("evidence"):
                lines.append("- **Evidence:**")
                for ev in diag["evidence"]:
                    lines.append(f"  - {ev}")
            if diag.get("notes"):
                lines.append(f"- **Notes:** {diag['notes']}")
            lines.append("")

        content = "\n".join(lines)
        path = Path(save_dir) / "diagnosis_report.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        logger.info("Diagnosis report saved → %s", path)
        return str(path)


# ── Helpers ──────────────────────────────────────────────────────


def _now() -> str:
    """ISO timestamp string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _summarize(data: dict[str, Any], max_str: int = 200) -> dict[str, Any]:
    """Create a lightweight summary of a dict, truncating long values."""
    out: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, str) and len(v) > max_str:
            out[k] = v[:max_str] + "..."
        elif isinstance(v, (list, dict)):
            try:
                s = json.dumps(v, default=str)
                out[k] = v if len(s) < 500 else f"<{type(v).__name__} len={len(v)}>"
            except (TypeError, ValueError):
                out[k] = f"<{type(v).__name__}>"
        else:
            out[k] = v
    return out


def _format_dict(d: dict) -> str:
    """Format a dict for markdown display."""
    parts = []
    for k, v in d.items():
        if isinstance(v, str) and len(v) > 100:
            v = v[:100] + "..."
        parts.append(f"`{k}`: {v}")
    return ", ".join(parts)
