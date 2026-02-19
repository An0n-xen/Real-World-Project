from __future__ import annotations
import json
import os
import re
import traceback
from pathlib import Path
from typing import Any, Callable, TypedDict

from langgraph.graph import StateGraph, END

from medagent.agents.analyzer import AnalyzerAgent
from medagent.agents.coding_agent import CodingAgent
from medagent.agents.decider import DeciderAgent
from medagent.agents.disease_setup import DiseaseSetupAgent
from medagent.agents.planner import PlannerAgent
from medagent.agents.summarizer import SummaryAgent
from medagent.config import get_settings
from medagent.logger import get_logger
from medagent.rag.retriever import MedicalRAG
from medagent.schemas import (
    DiagnosticIndicator,
    PlanStep,
    TaskConfig,
    ToolDefinition,
)
from medagent.tools.medical_tools import segment_optic_cup, segment_optic_disc
from medagent.tools.registry import ToolRegistry
from medagent.tracer import PipelineTracer
from medagent.knowledge.concept_linker import ConceptLinker

logger = get_logger(__name__)


# ── LangGraph state (typed dict for compatibility) ────────────────


class GraphState(TypedDict, total=False):
    """Shared state flowing through the LangGraph nodes."""

    # inputs
    disease_dir: str
    disease_name: str
    image_path: str
    patient_context: str

    # task-level
    task_config: dict
    toolset: list[dict]
    rag_context: str
    plan: list[dict]

    # case-level
    current_step_index: int
    save_dir: str
    step_results: dict
    brief_diagnosis: dict
    indicators: list[dict]

    # tool management
    tool_registry_names: list[str]
    gen_code_path: str

    # observability
    _tracer: Any  # PipelineTracer (Any to avoid TypedDict issues)

    # output
    diagnosis: dict
    error: str


# ── Helper ────────────────────────────────────────────────────────


def _snake(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip()).strip("_").lower()
    return s or "generated_fn"


def _command_to_fn_name(command: str) -> str:
    """Extract function name from a command string like ``segment_optic_disc()``."""
    match = re.match(r"(\w+)\s*\(", command)
    return match.group(1) if match else _snake(command)


# ── Singletons (lazy-initialised) ────────────────────────────────

_rag: MedicalRAG | None = None
_planner: PlannerAgent | None = None
_coder: CodingAgent | None = None
_analyzer: AnalyzerAgent | None = None
_summarizer: SummaryAgent | None = None
_decider: DeciderAgent | None = None
_setup_agent: DiseaseSetupAgent | None = None
_registry: ToolRegistry | None = None


def _get_rag() -> MedicalRAG:
    global _rag
    if _rag is None:
        _rag = MedicalRAG()
    return _rag


def _get_planner() -> PlannerAgent:
    global _planner
    if _planner is None:
        _planner = PlannerAgent()
    return _planner


def _get_coder() -> CodingAgent:
    global _coder
    if _coder is None:
        _coder = CodingAgent()
    return _coder


def _get_analyzer() -> AnalyzerAgent:
    global _analyzer
    if _analyzer is None:
        _analyzer = AnalyzerAgent()
    return _analyzer


def _get_summarizer() -> SummaryAgent:
    global _summarizer
    if _summarizer is None:
        _summarizer = SummaryAgent()
    return _summarizer


def _get_decider() -> DeciderAgent:
    global _decider
    if _decider is None:
        _decider = DeciderAgent()
    return _decider


def _get_setup_agent() -> DiseaseSetupAgent:
    global _setup_agent
    if _setup_agent is None:
        _setup_agent = DiseaseSetupAgent()
    return _setup_agent


def _get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        # Register built-in tools
        _registry.register("segment_optic_cup", segment_optic_cup)
        _registry.register("segment_optic_disc", segment_optic_disc)
    return _registry


_concept_linker: ConceptLinker | None = None


def _get_concept_linker() -> ConceptLinker:
    global _concept_linker
    if _concept_linker is None:
        _concept_linker = ConceptLinker()
    return _concept_linker


# ═══════════════════════════════════════════════════════════════════
# NODE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════


def load_config(state: GraphState) -> GraphState:
    """Node 1: Load task.json and toolset.json from the disease directory.

    If the disease directory doesn't exist, auto-creates it using
    DiseaseSetupAgent (online search + LLM synthesis).
    """
    disease_dir = state["disease_dir"]
    disease_name = state.get("disease_name", Path(disease_dir).name)
    logger.info("Loading config from %s", disease_dir)

    task_path = os.path.join(disease_dir, "task.json")
    toolset_path = os.path.join(disease_dir, "toolset.json")

    # Auto-setup if configs don't exist
    if not os.path.exists(task_path) or not os.path.exists(toolset_path):
        logger.info("Disease config not found — running auto-setup for '%s'", disease_name)
        settings = get_settings()
        setup_agent = _get_setup_agent()
        context = state.get("patient_context", "")
        disease_dir = setup_agent.setup(disease_name, settings.diseases_dir, patient_context=context)
        task_path = os.path.join(disease_dir, "task.json")
        toolset_path = os.path.join(disease_dir, "toolset.json")

    with open(task_path, "r", encoding="utf-8") as f:
        task_data = json.load(f)

    with open(toolset_path, "r", encoding="utf-8") as f:
        toolset_data = json.load(f)

    # Set up output directory
    settings = get_settings()
    save_dir = os.path.join(settings.output_dir, Path(disease_dir).name, "record")
    if state.get("image_path"):
        img_stem = Path(state["image_path"]).stem
        save_dir = os.path.join(save_dir, img_stem)
    os.makedirs(save_dir, exist_ok=True)

    logger.info(
        "Config loaded  disease=%s  tools=%d  save_dir=%s",
        task_data.get("disease"),
        len(toolset_data),
        save_dir,
    )

    return {
        **state,
        "disease_dir": disease_dir,
        "task_config": task_data,
        "toolset": toolset_data,
        "save_dir": save_dir,
        "current_step_index": 0,
        "step_results": {},
        "brief_diagnosis": {},
        "indicators": [],
    }


def retrieve_guidelines(state: GraphState) -> GraphState:
    """Node 2: RAG-retrieve relevant medical guidelines."""
    task_config = state["task_config"]
    disease = task_config.get("disease", "")

    rag = _get_rag()

    # Try to ingest guidelines if they exist
    disease_dir = state["disease_dir"]
    guidelines_dir = os.path.join(disease_dir, "guidelines")
    if os.path.isdir(guidelines_dir):
        rag.load_guidelines(guidelines_dir)

    query = f"How to diagnose {disease}? What are the clinical guidelines and criteria?"
    patient_context = state.get("patient_context", "")
    if patient_context:
        query += f" Patient context: {patient_context}"
    context = rag.query(query)

    logger.info("RAG context retrieved (%d chars)", len(context))
    return {**state, "rag_context": context}


def generate_plan(state: GraphState) -> GraphState:
    """Node 3: Generate a diagnostic plan using the Planner agent.

    Reuses an existing plan.json if one is found in the disease directory.
    """
    plan_path = os.path.join(state["disease_dir"], "plan.json")

    # Reuse cached plan if it exists
    if os.path.exists(plan_path):
        plan_data = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        logger.info("Reusing existing plan (%d steps) from %s", len(plan_data), plan_path)
        return {**state, "plan": plan_data}

    task = TaskConfig(**state["task_config"])
    toolset = [ToolDefinition(**t) for t in state["toolset"]]

    planner = _get_planner()
    patient_context = state.get("patient_context", "")
    steps = planner.plan(task, toolset, state.get("rag_context", ""), patient_context=patient_context)

    # Save plan
    plan_data = [s.model_dump() for s in steps]
    Path(plan_path).write_text(
        json.dumps(plan_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    logger.info("Diagnostic plan: %d steps → %s", len(steps), plan_path)
    return {**state, "plan": plan_data}


def generate_tools(state: GraphState) -> GraphState:
    """Node 4: Generate code for quantitative 'coding' steps."""
    plan = [PlanStep(**s) for s in state["plan"]]
    toolset = [ToolDefinition(**t) for t in state["toolset"]]
    task_config = state["task_config"]
    registry = _get_registry()
    coder = _get_coder()

    tool_by_id = {t.id: t for t in toolset}
    plan_by_id = {s.id: s for s in plan}

    code_path = os.path.join(state["disease_dir"], "tools", "GenCode.py")
    os.makedirs(os.path.dirname(code_path), exist_ok=True)
    # Always start fresh to avoid duplicate function definitions
    Path(code_path).write_text("# Generated code\n", encoding="utf-8")

    generated_names: list[str] = []

    for step in plan:
        tool_ids = step.tool or []
        is_coding = any(
            "coding" in (tool_by_id.get(tid, ToolDefinition(id=0, type="", function="")).type.lower())
            for tid in tool_ids
        )
        if not is_coding:
            continue

        fn_name = coder.generate_function(
            step=step,
            plan_by_id=plan_by_id,
            tool_by_id=tool_by_id,
            task_input_desc=task_config.get("input", ""),
            output_file=code_path,
        )
        generated_names.append(fn_name)

    # Load generated module and register functions
    if generated_names:
        module = coder.load_generated_module(code_path)
        if module:
            for fn_name in generated_names:
                fn = getattr(module, fn_name, None)
                if fn and callable(fn):
                    registry.register(fn_name, fn)

    logger.info("Generated %d tool functions", len(generated_names))
    return {
        **state,
        "tool_registry_names": registry.list_tools(),
        "gen_code_path": code_path,
    }


def execute_steps(state: GraphState) -> GraphState:
    """Node 5: Execute all plan steps (quantitative + qualitative)."""
    plan = [PlanStep(**s) for s in state["plan"]]
    toolset = [ToolDefinition(**t) for t in state["toolset"]]
    tool_by_id = {t.id: t for t in toolset}
    plan_by_id = {s.id: s for s in plan}

    registry = _get_registry()
    analyzer = _get_analyzer()
    summarizer = _get_summarizer()

    save_dir = state["save_dir"]
    image_path = state.get("image_path", "")
    patient_context = state.get("patient_context", "")
    step_results = dict(state.get("step_results", {}))
    brief_diagnosis: dict = dict(state.get("brief_diagnosis", {}))

    for step in plan:
        logger.info(
            "Executing step %d  type=%s  action=%s",
            step.id, step.action_type, step.action[:60],
        )

        if step.action_type.lower() == "quantitative":
            # Run quantitative tool
            tool_ids = step.tool or []
            for tid in tool_ids:
                tool = tool_by_id.get(tid)
                if tool is None:
                    logger.warning("Tool id %d not found in toolset", tid)
                    continue

                # Determine function name
                if "coding" in tool.type.lower():
                    fn_name = f"{_snake(step.action or step.output_type)}_{step.id}"
                else:
                    fn_name = _command_to_fn_name(tool.command) if tool.command else ""

                fn = registry.get(fn_name)
                if fn is None:
                    logger.warning("Function '%s' not registered, skipping", fn_name)
                    continue

                # Resolve dependencies
                deps: list[str] = []
                for dep_id in step.input_type:
                    if dep_id == 0:
                        deps.append(image_path)
                    else:
                        prev = plan_by_id.get(dep_id)
                        if prev:
                            deps.append(os.path.join(save_dir, prev.output_path))

                try:
                    if "coding" in tool.type.lower():
                        fn(deps, save_dir, step.output_path)
                    else:
                        primary = deps[0] if deps else image_path
                        fn(primary, save_dir, step.output_path)
                    step_results[f"step_{step.id}"] = "success"
                    logger.info("Step %d completed successfully", step.id)
                except Exception:
                    step_results[f"step_{step.id}"] = "error"
                    logger.exception("Step %d failed", step.id)

        elif step.action_type.lower() == "qualitative":
            # Check if result is already cached from a previous run
            step_key = f"step_{step.id}"
            output_path = os.path.join(save_dir, step.output_path)
            brief_path = os.path.join(save_dir, "brief_diagnosis.json")

            cached_diagnosis: dict = {}
            cached_brief: dict = {}
            if os.path.exists(output_path):
                try:
                    cached_diagnosis = json.loads(
                        Path(output_path).read_text(encoding="utf-8")
                    )
                except (json.JSONDecodeError, OSError):
                    pass
            if os.path.exists(brief_path):
                try:
                    cached_brief = json.loads(
                        Path(brief_path).read_text(encoding="utf-8")
                    )
                except (json.JSONDecodeError, OSError):
                    pass

            if step_key in cached_diagnosis and step_key in cached_brief:
                logger.info("Step %d using cached result — skipping VLM call", step.id)
                brief_diagnosis = cached_brief
                step_results[step_key] = "success"
                continue

            # Run qualitative VLM analysis
            image_inputs: list[str] = []
            text_inputs: list[str] = []

            for dep_id in step.input_type:
                if dep_id == 0:
                    image_inputs.append(image_path)
                else:
                    prev_step = plan_by_id.get(dep_id)
                    if prev_step:
                        prev_path = os.path.join(save_dir, prev_step.output_path)
                        if os.path.exists(prev_path):
                            ext = Path(prev_path).suffix.lower()
                            if ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}:
                                image_inputs.append(prev_path)
                            else:
                                try:
                                    text_inputs.append(
                                        Path(prev_path).read_text(encoding="utf-8")
                                    )
                                except Exception:
                                    pass

            try:
                result = analyzer.analyze_and_save(
                    prompt=step.action,
                    image_paths=image_inputs,
                    output_file=output_path,
                    field=step_key,
                    text_context=([patient_context] if patient_context else []) + text_inputs,
                )

                # Summarise
                summary = summarizer.summarize(
                    json.dumps(result, indent=2),
                    task_question=step.action,
                )
                # Save brief
                existing_brief: dict = {}
                if os.path.exists(brief_path):
                    try:
                        existing_brief = json.loads(
                            Path(brief_path).read_text(encoding="utf-8")
                        )
                    except (json.JSONDecodeError, OSError):
                        pass
                existing_brief[step_key] = summary
                Path(brief_path).write_text(
                    json.dumps(existing_brief, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                brief_diagnosis = existing_brief

                step_results[step_key] = "success"

                # Concept linking: extract medical concepts from VLM observation
                try:
                    linker = _get_concept_linker()
                    obs_text = json.dumps(result, default=str) if isinstance(result, dict) else str(result)
                    concepts_path = os.path.join(save_dir, "concepts.json")
                    linker.extract_and_save(obs_text, concepts_path, field=step_key)
                except Exception:
                    logger.debug("Concept linking skipped for step %d", step.id)
                logger.info("Step %d qualitative analysis complete", step.id)
            except Exception:
                step_results[step_key] = "error"
                logger.exception("Step %d qualitative analysis failed", step.id)

    return {
        **state,
        "step_results": step_results,
        "brief_diagnosis": brief_diagnosis,
    }


def collect_indicators(state: GraphState) -> GraphState:
    """Node 6: Collect 'final indicator' steps into the indicators list."""
    plan = [PlanStep(**s) for s in state["plan"]]
    brief = state.get("brief_diagnosis", {})

    indicators: list[dict] = []
    for step in plan:
        if step.output_type.lower() != "final indicator":
            continue
        indicators.append(
            {
                "indicator_name": step.action,
                "if_abnormal": brief.get(f"step_{step.id}", {}),
            }
        )

    logger.info("Collected %d final indicators", len(indicators))
    return {**state, "indicators": indicators}


def final_decision(state: GraphState) -> GraphState:
    """Node 7: Decider agent produces the final diagnosis.

    Reuses cached final_diagnosis.json if it already contains results.
    """
    task_config = state["task_config"]
    final_path = os.path.join(state["save_dir"], "final_diagnosis.json")

    # Check for cached result
    if os.path.exists(final_path):
        try:
            cached = json.loads(Path(final_path).read_text(encoding="utf-8"))
            if "overall" in cached:
                logger.info("Using cached final diagnosis — skipping Decider call")
                diag = cached["overall"]
                logger.info(
                    "Final diagnosis: %s (confidence=%.2f)",
                    diag.get("diagnosis", "?"),
                    diag.get("confidence", 0),
                )
                return {**state, "diagnosis": diag}
        except (json.JSONDecodeError, OSError):
            pass

    indicators = [DiagnosticIndicator(**ind) for ind in state["indicators"]]

    decider = _get_decider()
    patient_context = state.get("patient_context", "")
    task_input = task_config.get("input", "")
    if patient_context:
        task_input += f"\nPatient context: {patient_context}"
    result = decider.decide_and_save(
        indicators=indicators,
        output_file=final_path,
        task_input=task_input,
        disease_goal=task_config.get("disease", ""),
    )

    logger.info("Final diagnosis: %s (confidence=%.2f)", result.diagnosis, result.confidence)
    return {**state, "diagnosis": result.model_dump()}


# ═══════════════════════════════════════════════════════════════════
# GRAPH CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════


def _traced(node_fn: Callable, node_name: str) -> Callable:
    """Wrap a node function with tracing (start/end + error capture)."""

    def wrapper(state: GraphState) -> GraphState:
        tracer: PipelineTracer | None = state.get("_tracer")
        inputs = {
            k: v for k, v in state.items()
            if k not in ("_tracer",) and isinstance(v, (str, int, float, bool))
        }
        if tracer:
            tracer.start_node(node_name, inputs=inputs)
        try:
            result = node_fn(state)
            if tracer:
                outputs = {
                    k: v for k, v in result.items()
                    if k not in ("_tracer",) and isinstance(v, (str, int, float, bool))
                }
                tracer.end_node(node_name, outputs=outputs)
            return result
        except Exception as exc:
            if tracer:
                tracer.end_node(node_name, error=f"{exc.__class__.__name__}: {exc}")
            raise

    wrapper.__name__ = node_name
    return wrapper


def build_workflow() -> StateGraph:
    """Build and return the compiled MedAgent-Pro LangGraph workflow."""
    graph = StateGraph(GraphState)

    # Add nodes (wrapped with tracing)
    graph.add_node("load_config", _traced(load_config, "load_config"))
    graph.add_node("retrieve_guidelines", _traced(retrieve_guidelines, "retrieve_guidelines"))
    graph.add_node("generate_plan", _traced(generate_plan, "generate_plan"))
    graph.add_node("generate_tools", _traced(generate_tools, "generate_tools"))
    graph.add_node("execute_steps", _traced(execute_steps, "execute_steps"))
    graph.add_node("collect_indicators", _traced(collect_indicators, "collect_indicators"))
    graph.add_node("final_decision", _traced(final_decision, "final_decision"))

    # Define linear flow
    graph.set_entry_point("load_config")
    graph.add_edge("load_config", "retrieve_guidelines")
    graph.add_edge("retrieve_guidelines", "generate_plan")
    graph.add_edge("generate_plan", "generate_tools")
    graph.add_edge("generate_tools", "execute_steps")
    graph.add_edge("execute_steps", "collect_indicators")
    graph.add_edge("collect_indicators", "final_decision")
    graph.add_edge("final_decision", END)

    logger.info("MedAgent-Pro workflow graph built (7 nodes)")
    return graph


def compile_workflow():
    """Build, compile, and return the runnable workflow."""
    graph = build_workflow()
    return graph.compile()


def run_diagnosis(
    disease_dir: str,
    image_path: str = "",
    disease_name: str = "",
    patient_context: str = "",
) -> dict:
    """Run the full MedAgent-Pro diagnostic pipeline.

    Args:
        disease_dir: Path to the disease configuration directory
                     (containing task.json, toolset.json, guidelines/).
        image_path:  Path to the patient's medical image.
        disease_name: Human-readable disease name for auto-setup.
        patient_context: Additional patient context (history, symptoms, labs).

    Returns:
        The final graph state dict containing the diagnosis.
    """
    if not disease_name:
        disease_name = Path(disease_dir).name.replace("_", " ")

    logger.info("=" * 60)
    logger.info("MedAgent-Pro Diagnosis Pipeline")
    logger.info("  disease      = %s", disease_name)
    logger.info("  disease_dir  = %s", disease_dir)
    logger.info("  image_path   = %s", image_path)
    if patient_context:
        logger.info("  context      = %s", patient_context[:100])
    logger.info("=" * 60)

    # Create tracer for observability
    tracer = PipelineTracer(
        disease=disease_name,
        image_path=image_path,
        patient_context=patient_context,
    )

    workflow = compile_workflow()
    initial_state: GraphState = {
        "disease_dir": disease_dir,
        "disease_name": disease_name,
        "image_path": image_path,
        "patient_context": patient_context,
        "_tracer": tracer,
    }

    result = workflow.invoke(initial_state)

    # Record final diagnosis and save trace + report
    if result.get("diagnosis"):
        tracer.set_final_diagnosis(result["diagnosis"])

    save_dir = result.get("save_dir", "")
    if save_dir:
        tracer.save_trace(save_dir)
        tracer.generate_report(save_dir)

    logger.info("=" * 60)
    logger.info("Pipeline complete")
    if result.get("diagnosis"):
        diag = result["diagnosis"]
        logger.info(
            "  Diagnosis:  %s  (confidence=%.2f)",
            diag.get("diagnosis", "?"),
            diag.get("confidence", 0),
        )
    logger.info("=" * 60)

    return result
