from __future__ import annotations

import asyncio
import json
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from medagent.config import get_settings
from medagent.logger import get_logger
from medagent.schemas import (
    DiagnosisResult, DiagnosticIndicator, ReasoningStep, WeightedIndicator,
)

logger = get_logger(__name__)

DECIDER_SYSTEM_PROMPT = """
    You are a clinical decision assistant. Given a set of diagnostic indicators 
    (each with whether abnormality was detected), you must:

    1. Propose reasonable clinical weights for each indicator (sum to 1.0).
    2. Set a diagnostic threshold in [0, 1].
    3. Determine the final diagnosis.
    4. Provide a step-by-step reasoning chain explaining HOW you reached your conclusion.

    Output a JSON object with:
    - "weights": list of {"indicator_name": str, "weight": float}
    - "threshold": float
    - "diagnosis": "positive" or "negative"
    - "confidence": float between 0 and 1
    - "evidence": list of strings explaining key reasons
    - "notes": optional short string with caveats
    - "reasoning_chain": list of objects, each with:
        - "observation": what was observed (str)
        - "clinical_significance": why this matters clinically (str)
        - "supports_diagnosis": true if it supports positive diagnosis (bool)
        - "confidence_contribution": how much it contributes to confidence (float 0-1)
"""


class DeciderAgent:
    """Synthesise diagnostic indicators into a final clinical decision."""

    def __init__(self) -> None:
        settings = get_settings()
        self._llm = ChatOpenAI(
            model=settings.text_llm_model,
            api_key=settings.deepinfra_api_key,
            base_url=settings.deepinfra_base_url,
            temperature=0,
            max_tokens=2048,
            seed=42,
        )
        logger.info("DeciderAgent ready  model=%s", settings.text_llm_model)

    def decide(
        self,
        indicators: list[DiagnosticIndicator],
        task_input: str = "",
        disease_goal: str = "",
    ) -> DiagnosisResult:
        """Produce a final diagnosis from the collected *indicators*."""
        indicators_json = json.dumps(
            [ind.model_dump() for ind in indicators], indent=2
        )

        prompt = (
            "You are making a final clinical decision.\n\n"
            f"**Patient input:** {task_input}\n"
            f"**Diagnostic goal:** {disease_goal}\n\n"
            f"**Collected indicators:**\n```json\n{indicators_json}\n```\n\n"
            "Propose weights, threshold, and final diagnosis. Return ONLY JSON."
        )

        logger.info(
            "Final decision  indicators=%d  goal=%s",
            len(indicators),
            disease_goal,
        )

        response = self._llm.invoke([
            SystemMessage(content=DECIDER_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Failed to parse decider response: %s", raw[:500])
            return DiagnosisResult(
                diagnosis="error",
                notes="Failed to parse LLM response",
            )

        # Compute weighted score
        weights = [
            WeightedIndicator(**w) for w in data.get("weights", [])
        ]
        weighted_score = 0.0
        for w in weights:
            # Find matching indicator
            for ind in indicators:
                if ind.indicator_name == w.indicator_name:
                    is_abnormal = ind.if_abnormal.get("abnormality_present", False)
                    weighted_score += w.weight * (1.0 if is_abnormal else 0.0)
                    break

        # Parse reasoning chain
        reasoning_chain = []
        for rs in data.get("reasoning_chain", []):
            try:
                reasoning_chain.append(ReasoningStep(
                    observation=rs.get("observation", ""),
                    clinical_significance=rs.get("clinical_significance", ""),
                    supports_diagnosis=rs.get("supports_diagnosis", True),
                    confidence_contribution=rs.get("confidence_contribution", 0.0),
                ))
            except Exception:
                pass

        result = DiagnosisResult(
            diagnosis=data.get("diagnosis", "unknown"),
            confidence=data.get("confidence", 0.0),
            threshold=data.get("threshold", 0.5),
            weighted_score=weighted_score,
            weights=weights,
            evidence=data.get("evidence", []),
            notes=data.get("notes", ""),
            reasoning_chain=reasoning_chain,
        )

        logger.info(
            "Diagnosis: %s  confidence=%.2f  weighted_score=%.2f  threshold=%.2f  reasoning_steps=%d",
            result.diagnosis,
            result.confidence,
            result.weighted_score,
            result.threshold,
            len(reasoning_chain),
        )
        return result

    def decide_and_save(
        self,
        indicators: list[DiagnosticIndicator],
        output_file: str | Path,
        task_input: str = "",
        disease_goal: str = "",
        field: str = "overall",
    ) -> DiagnosisResult:
        """Run decision and save to *output_file* under *field*.

        File writes are skipped when MongoDB is enabled.
        """
        from medagent.config import get_settings

        result = self.decide(indicators, task_input, disease_goal)

        if get_settings().mongodb_enabled:
            logger.info("Final diagnosis ready (MongoDB mode — skipping file write)")
            return result

        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        existing: dict = {}
        if output_file.exists():
            try:
                existing = json.loads(output_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        existing[field] = result.model_dump()
        output_file.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Final diagnosis saved → %s [%s]", output_file, field)

        # Save reasoning trace separately for easy inspection
        if result.reasoning_chain:
            trace_path = output_file.parent / "reasoning_trace.json"
            trace_data = {
                "disease_goal": disease_goal,
                "diagnosis": result.diagnosis,
                "confidence": result.confidence,
                "reasoning_chain": [s.model_dump() for s in result.reasoning_chain],
            }
            trace_path.write_text(
                json.dumps(trace_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Reasoning trace saved → %s (%d steps)", trace_path, len(result.reasoning_chain))

        return result

    # ── Async variants ──────────────────────────────────────────────

    async def adecide(
        self,
        indicators: list[DiagnosticIndicator],
        task_input: str = "",
        disease_goal: str = "",
    ) -> DiagnosisResult:
        """Async version of :meth:`decide` — uses ``ainvoke``."""
        indicators_json = json.dumps(
            [ind.model_dump() for ind in indicators], indent=2
        )

        prompt = (
            "You are making a final clinical decision.\n\n"
            f"**Patient input:** {task_input}\n"
            f"**Diagnostic goal:** {disease_goal}\n\n"
            f"**Collected indicators:**\n```json\n{indicators_json}\n```\n\n"
            "Propose weights, threshold, and final diagnosis. Return ONLY JSON."
        )

        logger.info(
            "[async] Final decision  indicators=%d  goal=%s",
            len(indicators),
            disease_goal,
        )

        response = await self._llm.ainvoke([
            SystemMessage(content=DECIDER_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("[async] Failed to parse decider response: %s", raw[:500])
            return DiagnosisResult(
                diagnosis="error",
                notes="Failed to parse LLM response",
            )

        weights = [WeightedIndicator(**w) for w in data.get("weights", [])]
        weighted_score = 0.0
        for w in weights:
            for ind in indicators:
                if ind.indicator_name == w.indicator_name:
                    is_abnormal = ind.if_abnormal.get("abnormality_present", False)
                    weighted_score += w.weight * (1.0 if is_abnormal else 0.0)
                    break

        reasoning_chain = []
        for rs in data.get("reasoning_chain", []):
            try:
                reasoning_chain.append(ReasoningStep(
                    observation=rs.get("observation", ""),
                    clinical_significance=rs.get("clinical_significance", ""),
                    supports_diagnosis=rs.get("supports_diagnosis", True),
                    confidence_contribution=rs.get("confidence_contribution", 0.0),
                ))
            except Exception:
                pass

        result = DiagnosisResult(
            diagnosis=data.get("diagnosis", "unknown"),
            confidence=data.get("confidence", 0.0),
            threshold=data.get("threshold", 0.5),
            weighted_score=weighted_score,
            weights=weights,
            evidence=data.get("evidence", []),
            notes=data.get("notes", ""),
            reasoning_chain=reasoning_chain,
        )

        logger.info(
            "[async] Diagnosis: %s  confidence=%.2f  weighted_score=%.2f  threshold=%.2f  reasoning_steps=%d",
            result.diagnosis, result.confidence, result.weighted_score,
            result.threshold, len(reasoning_chain),
        )
        return result

    async def adecide_and_save(
        self,
        indicators: list[DiagnosticIndicator],
        output_file: str | Path,
        task_input: str = "",
        disease_goal: str = "",
        field: str = "overall",
    ) -> DiagnosisResult:
        """Async version of :meth:`decide_and_save`.

        File writes are skipped when MongoDB is enabled.
        """
        from medagent.config import get_settings

        result = await self.adecide(indicators, task_input, disease_goal)

        if get_settings().mongodb_enabled:
            logger.info("[async] Final diagnosis ready (MongoDB mode — skipping file write)")
            return result

        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        existing: dict = {}
        if output_file.exists():
            try:
                existing = json.loads(output_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        existing[field] = result.model_dump()
        await asyncio.to_thread(
            output_file.write_text,
            json.dumps(existing, indent=2, ensure_ascii=False),
            "utf-8",
        )
        logger.info("[async] Final diagnosis saved → %s [%s]", output_file, field)

        if result.reasoning_chain:
            trace_path = output_file.parent / "reasoning_trace.json"
            trace_data = {
                "disease_goal": disease_goal,
                "diagnosis": result.diagnosis,
                "confidence": result.confidence,
                "reasoning_chain": [s.model_dump() for s in result.reasoning_chain],
            }
            await asyncio.to_thread(
                trace_path.write_text,
                json.dumps(trace_data, indent=2, ensure_ascii=False),
                "utf-8",
            )
            logger.info(
                "[async] Reasoning trace saved → %s (%d steps)",
                trace_path, len(result.reasoning_chain),
            )

        return result
