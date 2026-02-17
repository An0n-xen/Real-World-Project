from __future__ import annotations

import json
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from medagent.config import get_settings
from medagent.logger import get_logger
from medagent.schemas import DiagnosisResult, DiagnosticIndicator, WeightedIndicator

logger = get_logger(__name__)

DECIDER_SYSTEM_PROMPT = """
    You are a clinical decision assistant. Given a set of diagnostic indicators 
    (each with whether abnormality was detected), you must:

    1. Propose reasonable clinical weights for each indicator (sum to 1.0).
    2. Set a diagnostic threshold in [0, 1].
    3. Determine the final diagnosis.

    Output a JSON object with:
    - "weights": list of {"indicator_name": str, "weight": float}
    - "threshold": float
    - "diagnosis": "positive" or "negative"
    - "confidence": float between 0 and 1
    - "evidence": list of strings explaining key reasons
    - "notes": optional short string with caveats
"""


class DeciderAgent:
    """Synthesise diagnostic indicators into a final clinical decision."""

    def __init__(self) -> None:
        settings = get_settings()
        self._llm = ChatOpenAI(
            model=settings.text_llm_model,
            api_key=settings.deepinfra_api_key,
            base_url=settings.deepinfra_base_url,
            temperature=0.1,
            max_tokens=2048,
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

        result = DiagnosisResult(
            diagnosis=data.get("diagnosis", "unknown"),
            confidence=data.get("confidence", 0.0),
            threshold=data.get("threshold", 0.5),
            weighted_score=weighted_score,
            weights=weights,
            evidence=data.get("evidence", []),
            notes=data.get("notes", ""),
        )

        logger.info(
            "Diagnosis: %s  confidence=%.2f  weighted_score=%.2f  threshold=%.2f",
            result.diagnosis,
            result.confidence,
            result.weighted_score,
            result.threshold,
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
        """Run decision and save to *output_file* under *field*."""
        result = self.decide(indicators, task_input, disease_goal)

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
        return result
