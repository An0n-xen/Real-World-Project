from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

from medagent.config import configure_langsmith, get_settings
from medagent.logger import get_logger

logger = get_logger("medagent.cli")


def cmd_ingest(args: argparse.Namespace) -> None:
    """Ingest medical guidelines into the RAG vector store."""
    from medagent.rag.retriever import MedicalRAG

    settings = get_settings()

    # Get guidelines directory
    guidelines_dir = os.path.join(settings.diseases_dir, args.disease, "guidelines")

    if not os.path.isdir(guidelines_dir):
        logger.error("Guidelines directory not found: %s", guidelines_dir)
        sys.exit(1)

    rag = MedicalRAG()
    count = rag.load_guidelines(guidelines_dir)
    logger.info("Ingested %d chunks from %s", count, guidelines_dir)


def cmd_plan(args: argparse.Namespace) -> None:
    """Generate a diagnostic plan for a disease."""
    from medagent.agents.planner import PlannerAgent
    from medagent.rag.retriever import MedicalRAG
    from medagent.schemas import TaskConfig, ToolDefinition

    settings = get_settings()

    # Get disease directory
    disease_dir = os.path.join(settings.diseases_dir, args.disease)
    task_path = os.path.join(disease_dir, "task.json")
    toolset_path = os.path.join(disease_dir, "toolset.json")

    if not os.path.exists(task_path):
        logger.error("task.json not found in %s", disease_dir)
        sys.exit(1)

    with open(task_path, "r", encoding="utf-8") as f:
        task = TaskConfig(**json.load(f))

    with open(toolset_path, "r", encoding="utf-8") as f:
        toolset = [ToolDefinition(**t) for t in json.load(f)]

    # RAG context
    rag = MedicalRAG()
    guidelines_dir = os.path.join(disease_dir, "guidelines")
    if os.path.isdir(guidelines_dir):
        rag.load_guidelines(guidelines_dir)
    rag_context = rag.query(f"How to diagnose {task.disease}?")

    planner = PlannerAgent()
    steps = planner.plan(task, toolset, rag_context)
    plan_path = planner.save_plan(steps, disease_dir)

    logger.info("Plan saved to %s", plan_path)

    # Print plan summary
    for step in steps:
        logger.info(
            "  Step %d [%s] %s → %s",
            step.id,
            step.action_type,
            step.action[:50],
            step.output_type,
        )


def cmd_diagnose(args: argparse.Namespace) -> None:
    """Run the full diagnostic pipeline."""
    from medagent.workflow import run_diagnosis

    settings = get_settings()
    disease_name = args.disease
    dir_name = disease_name.lower().replace(" ", "_").replace("-", "_")
    disease_dir = os.path.join(settings.diseases_dir, dir_name)

    image_path = args.image or ""
    if image_path and not os.path.exists(image_path):
        logger.error("Image file not found: %s", image_path)
        sys.exit(1)

    # Handle context: inline text or @filepath
    patient_context = args.context or ""
    if patient_context.startswith("@"):
        ctx_file = patient_context[1:]
        if os.path.exists(ctx_file):
            patient_context = Path(ctx_file).read_text(encoding="utf-8")
            logger.info("Loaded context from file: %s", ctx_file)
        else:
            logger.error("Context file not found: %s", ctx_file)
            sys.exit(1)

    result = run_diagnosis(
        disease_dir, image_path,
        disease_name=disease_name,
        patient_context=patient_context,
    )

    # Print final diagnosis
    diagnosis = result.get("diagnosis", {})
    if diagnosis:
        logger.info("━" * 50)
        logger.info("FINAL DIAGNOSIS")
        logger.info("━" * 50)
        logger.info("  Result:     %s", diagnosis.get("diagnosis", "unknown"))
        logger.info("  Confidence: %.2f", diagnosis.get("confidence", 0))
        logger.info("  Score:      %.2f / %.2f (threshold)",
                     diagnosis.get("weighted_score", 0),
                     diagnosis.get("threshold", 0.5))

        evidence = diagnosis.get("evidence", [])
        if evidence:
            logger.info("  Evidence:")
            for e in evidence:
                logger.info("    • %s", e)

        notes = diagnosis.get("notes", "")
        if notes:
            logger.info("  Notes: %s", notes)
        logger.info("━" * 50)

        # Also save to output dir
        output_path = os.path.join(
            result.get("save_dir", settings.output_dir),
            "final_diagnosis.json",
        )
        logger.info("Full results saved to: %s", output_path)


def main() -> None:
    """Entry point."""
    # Configure LangSmith before any LangChain component initialises
    configure_langsmith()

    parser = argparse.ArgumentParser(
        prog="medagent-pro",
        description="MedAgent-Pro: Evidence-based multi-modal medical diagnosis",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Ingest medical guidelines into RAG")
    p_ingest.add_argument("--disease", required=True, help="Disease name (directory under diseases/)")

    # plan
    p_plan = subparsers.add_parser("plan", help="Generate diagnostic plan")
    p_plan.add_argument("--disease", required=True, help="Disease name")

    # diagnose
    p_diag = subparsers.add_parser("diagnose", help="Run full diagnostic pipeline")
    p_diag.add_argument("--disease", required=True, help="Disease name")
    p_diag.add_argument("--image", default="", help="Path to patient medical image")
    p_diag.add_argument(
        "--context", default="",
        help="Patient context (history, symptoms, labs). Use @filepath to load from a file.",
    )

    args = parser.parse_args()

    if args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "plan":
        cmd_plan(args)
    elif args.command == "diagnose":
        cmd_diagnose(args)


if __name__ == "__main__":
    main()