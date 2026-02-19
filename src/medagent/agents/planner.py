from __future__ import annotations
import json
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from medagent.config import get_settings
from medagent.logger import get_logger
from medagent.schemas import PlanStep, TaskConfig, ToolDefinition

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """
        You are a medical diagnostic planning agent. Your role is to create a precise, 
        step-by-step diagnostic workflow using ONLY the tools available in the toolset.

        You must produce plans that follow modern clinical diagnostic principles:
        1. Each step should have a clear purpose and dependency chain.
        2. Quantitative measurements must always be followed by qualitative interpretation.
        3. All indicators should be systematically evaluated before final diagnosis.

        CRITICAL RULES:
        - id starts from 1 and increases by 1
        - tool is an ARRAY of integers (tool ids from the toolset)
        - action_type is a STRING: 'qualitative' or 'quantitative'
        - input_type is an ARRAY of integers; use 0 for raw/original inputs, or a prior step's id
        - output_type MUST be EXACTLY one of: 'intermediate result' or 'final indicator'
        - For any non-image output, set output_path EXACTLY to 'diagnosis.json'
        - Use a VLM tool for qualitative indicators; list EACH indicator as a SEPARATE step
        - Qualitative observation steps MUST set output_type='final indicator'
        - Segmentation/measurement steps MUST set output_type='intermediate result'
        and be followed by a qualitative VLM judgement step
        - Steps must follow strict logical order with no forward references

        Return ONLY a valid JSON array of step objects.
"""


class PlannerAgent:
    """Generate a disease-level diagnostic plan.

    Uses RAG-retrieved medical guidelines + the available toolset to produce
    a structured plan that the orchestrator will execute per-patient.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._llm = ChatOpenAI(
            model=settings.text_llm_model,
            api_key=settings.deepinfra_api_key,
            base_url=settings.deepinfra_base_url,
            temperature=0,
            max_tokens=4096,
            seed=42,
        )
        logger.info("PlannerAgent ready  model=%s", settings.text_llm_model)

    def plan(
        self,
        task: TaskConfig,
        toolset: list[ToolDefinition],
        rag_context: str = "",
        patient_context: str = "",
    ) -> list[PlanStep]:
        """Generate a diagnostic plan and return validated ``PlanStep`` list."""
        toolset_json = json.dumps(
            [t.model_dump() for t in toolset], indent=2
        )

        user_prompt = (
            "Plan a step-by-step, executable diagnostic workflow.\n\n"
            f"**Patient input:** {task.input}\n"
            f"**Diagnostic goal:** {task.disease}\n\n"
        )

        if patient_context:
            user_prompt += (
                "**Patient context (history, symptoms, labs):**\n"
                f"{patient_context}\n\n"
            )

        if rag_context:
            user_prompt += (
                "**Relevant clinical guidelines (from RAG):**\n"
                f"{rag_context}\n\n"
            )

        user_prompt += (
            f"**Available toolset:**\n```json\n{toolset_json}\n```\n\n"
            "Produce a JSON array of step objects. Return ONLY the JSON."
        )

        logger.info("Generating diagnostic plan for: %s", task.disease)

        response = self._llm.invoke([
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        raw = response.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]  # skip opening fence
            raw = raw.rsplit("```", 1)[0]  # strip closing fence

        try:
            steps_data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse plan JSON: %s\nRaw: %s", exc, raw[:500])
            raise

        steps = [PlanStep.model_validate(s) for s in steps_data]
        logger.info("Plan generated: %d steps", len(steps))

        for step in steps:
            logger.debug(
                "  Step %d  type=%-12s  action=%s",
                step.id,
                step.action_type,
                step.action[:60],
            )

        return steps

    def save_plan(
        self,
        steps: list[PlanStep],
        output_dir: str | Path,
        filename: str = "plan.json",
    ) -> Path:
        """Persist the plan to a JSON file."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / filename

        data = [s.model_dump() for s in steps]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Plan saved → %s", path)
        return path
