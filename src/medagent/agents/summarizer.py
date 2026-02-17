from __future__ import annotations
import json
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from medagent.config import get_settings
from medagent.logger import get_logger

logger = get_logger(__name__)

SUMMARY_SYSTEM_PROMPT = """\
    You are a clinical summarisation assistant. Given detailed diagnostic analysis 
    text, produce a concise clinical summary.

    Output a JSON object with:
    - "summary": 1-3 sentence clinical summary
    - "abnormality_present": true/false
    - "severity": "none" | "mild" | "moderate" | "severe"
    - "key_findings": list of short strings
"""


class SummaryAgent:
    """Summarise detailed qualitative analysis into brief diagnostic notes."""

    def __init__(self) -> None:
        settings = get_settings()
        self._llm = ChatOpenAI(
            model=settings.text_llm_model,
            api_key=settings.deepinfra_api_key,
            base_url=settings.deepinfra_base_url,
            temperature=0.1,
            max_tokens=1024,
        )
        logger.info("SummaryAgent ready  model=%s", settings.text_llm_model)

    def summarize(self, text: str, task_question: str = "") -> dict:
        """Return a structured summary dict from *text*."""
        prompt = f"Summarise the following diagnostic analysis.\n\n{text}"
        if task_question:
            prompt += (
                f"\n\nThe diagnostic question is: {task_question}. "
                "Does this patient show abnormality?"
            )

        logger.info("Summarising analysis (%d chars)", len(text))

        response = self._llm.invoke([
            SystemMessage(content=SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Summary response not valid JSON, wrapping")
            result = {
                "summary": raw,
                "abnormality_present": False,
                "severity": "none",
                "key_findings": [],
            }

        logger.info(
            "Summary: abnormal=%s  severity=%s",
            result.get("abnormality_present"),
            result.get("severity"),
        )
        return result

    def summarize_and_save(
        self,
        input_file: str | Path,
        output_file: str | Path,
        field: str,
        task_question: str = "",
    ) -> dict:
        """Read analysis from *input_file*, summarise, and save under *field*."""
        input_file = Path(input_file)
        if not input_file.exists():
            logger.warning("Input file not found: %s", input_file)
            return {}

        data = json.loads(input_file.read_text(encoding="utf-8"))

        # Flatten the data to a text representation
        if isinstance(data, dict):
            text = json.dumps(data, indent=2)
        else:
            text = str(data)

        result = self.summarize(text, task_question)

        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        existing: dict = {}
        if output_file.exists():
            try:
                existing = json.loads(output_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        existing[field] = result
        output_file.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Brief diagnosis saved → %s [%s]", output_file, field)
        return result
