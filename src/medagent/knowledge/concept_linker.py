from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from medagent.config import get_settings
from medagent.logger import get_logger

logger = get_logger(__name__)


# ── Schemas ──────────────────────────────────────────────────────


class MedicalConcept(BaseModel):
    """A single extracted medical concept."""

    name: str = Field(..., description="Standardized concept name")
    category: str = Field(
        default="finding",
        description="Category: symptom, finding, condition, measurement, anatomy",
    )
    original_text: str = Field(default="", description="Original text span")
    relevance: str = Field(default="", description="Why this concept is relevant")


# ── Extraction prompt ────────────────────────────────────────────


CONCEPT_EXTRACTION_PROMPT = """\
You are a medical concept extraction system. Given clinical observation text,
extract the TOP 5 most medically significant concepts. Return ONLY a valid JSON array.

Each object must have:
- "name": standardized medical term
- "category": one of "symptom", "finding", "condition", "measurement", "anatomy"
- "original_text": exact text span (keep short)
- "relevance": one-sentence clinical relevance

Return ONLY valid JSON. No markdown, no explanation. Keep values short to avoid JSON errors.
"""


# ── Linker ───────────────────────────────────────────────────────


class ConceptLinker:
    """Extract structured medical concepts from clinical text using LLM."""

    def __init__(self) -> None:
        settings = get_settings()
        self._llm = ChatOpenAI(
            model=settings.text_llm_model,
            api_key=settings.deepinfra_api_key,
            base_url=settings.deepinfra_base_url,
            temperature=0,
            max_tokens=1024,
            seed=42,
        )
        logger.info("ConceptLinker ready  model=%s", settings.text_llm_model)

    def extract(self, text: str) -> list[MedicalConcept]:
        """Extract medical concepts from observation text."""
        if not text or len(text.strip()) < 10:
            return []

        try:
            response = self._llm.invoke([
                SystemMessage(content=CONCEPT_EXTRACTION_PROMPT),
                HumanMessage(content=f"Extract medical concepts from:\n\n{text[:1500]}"),
            ])

            raw = response.content.strip()
            # Strip markdown fences
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                raw = raw.rsplit("```", 1)[0].strip()

            # Try direct parse first
            try:
                concepts_data = json.loads(raw)
            except json.JSONDecodeError:
                # Fallback: extract the JSON array via regex
                match = re.search(r"\[.*\]", raw, re.DOTALL)
                if match:
                    concepts_data = json.loads(match.group())
                else:
                    logger.warning("Could not extract JSON array from response")
                    return []

            concepts = [MedicalConcept(**c) for c in concepts_data]
            logger.info("Extracted %d medical concepts", len(concepts))
            return concepts

        except Exception:
            logger.exception("Concept extraction failed")
            return []

    def extract_and_save(
        self,
        text: str,
        output_file: str | Path,
        field: str = "concepts",
    ) -> list[MedicalConcept]:
        """Extract concepts and save to a JSON file.

        File writes are skipped when MongoDB is enabled.
        """
        from medagent.config import get_settings

        concepts = self.extract(text)

        if get_settings().mongodb_enabled:
            logger.info("Concepts extracted (%d) — skipping file write (MongoDB mode)", len(concepts))
            return concepts

        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        existing: dict = {}
        if output_file.exists():
            try:
                existing = json.loads(output_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        existing[field] = [c.model_dump() for c in concepts]
        output_file.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Concepts saved → %s [%s] (%d concepts)", output_file, field, len(concepts))
        return concepts
