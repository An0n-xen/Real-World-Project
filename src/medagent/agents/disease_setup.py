from __future__ import annotations
import json
import os
from pathlib import Path

from duckduckgo_search import DDGS
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from medagent.config import get_settings
from medagent.logger import get_logger

logger = get_logger(__name__)

GUIDELINE_SYNTH_PROMPT = """
    You are a medical knowledge synthesis agent. Given web search results about
    a disease, produce a comprehensive clinical guideline document in Markdown.

    The guideline MUST include:
    1. Overview of the disease
    2. Key diagnostic criteria / classification systems
    3. Clinical signs and symptoms
    4. Recommended diagnostic workflow (step-by-step)
    5. Quantitative thresholds or measurements (if applicable)
    6. Differential diagnosis considerations

    Write in a professional clinical tone. Use headers, bullet points, and tables
    where appropriate. Be specific about measurable indicators and thresholds.
    Output ONLY the Markdown content, no preamble.
"""

TOOLSET_GEN_PROMPT = """
    You are a medical AI toolset designer. Given a disease name and its clinical
    guidelines, generate a JSON array of tools needed for AI-assisted diagnosis.

    RULES:
    - Tool id 1 MUST always be a VLM (Vision Language Model) for qualitative analysis
    - The last tool MUST always be a coding module for indicator computation
    - Between them, add disease-specific tools if quantitative analysis is needed
      (e.g., segmentation models for specific anatomical structures)
    - Each tool object must have: id, type, function, input, output
    - Segmentation tools must also have a "command" field with the function call

    Example for glaucoma:
    [
        {"id": 1, "type": "Vision Language Model (VLM)", "function": "Make qualitative analysis",
         "input": "Any image, text or multi-modal input",
         "output": "Qualitative analysis or description of certain features"},
        {"id": 2, "type": "segmentation model", "function": "Segment the optic disc",
         "input": "Original fundus image", "output": "Grayscale segmentation mask",
         "command": "segment_optic_disc()"},
        {"id": 3, "type": "coding module", "function": "Write simple code for indicator computation"}
    ]

    For diseases where no specific segmentation is applicable, just include VLM + coding module.
    Return ONLY the JSON array.
"""

TASK_GEN_PROMPT = """
    You are a medical task configuration agent. Given a disease name, generate a
    JSON object with exactly two fields:
    - "input": description of the expected patient input (e.g., "Fundus image of the patient")
    - "disease": diagnostic goal statement (e.g., "Diagnose potential glaucoma")

    Return ONLY the JSON object, no markdown fences.
"""


class DiseaseSetupAgent:
    """Auto-bootstraps disease configs by searching online and using LLM synthesis."""

    def __init__(self) -> None:
        settings = get_settings()
        self._llm = ChatOpenAI(
            model=settings.text_llm_model,
            api_key=settings.deepinfra_api_key,
            base_url=settings.deepinfra_base_url,
            temperature=0,
            max_tokens=4096,
            model_kwargs={"seed": 42},
        )
        self._ddgs = DDGS()
        logger.info("DiseaseSetupAgent ready  model=%s", settings.text_llm_model)

    def _search_guidelines(self, disease: str, patient_context: str = "", max_results: int = 8) -> str:
        """Search DuckDuckGo for clinical guidelines and return combined snippets."""
        query = f"clinical diagnostic guidelines criteria for {disease}"
        if patient_context:
            # Add key terms from context to refine search
            query += f" {patient_context[:100]}"
        logger.info("Searching online: %s", query)

        try:
            results = list(self._ddgs.text(query, max_results=max_results))
        except Exception:
            logger.exception("DuckDuckGo search failed")
            results = []

        if not results:
            logger.warning("No search results found — will rely on LLM knowledge")
            return f"No search results available. Use your medical knowledge about {disease}."

        snippets = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            snippets.append(f"### {title}\nSource: {href}\n{body}")

        combined = "\n\n".join(snippets)
        logger.info("Retrieved %d search results (%d chars)", len(results), len(combined))
        return combined

    def _synthesize_guidelines(self, disease: str, search_results: str, patient_context: str = "") -> str:
        """Use LLM to synthesize clinical guidelines from search results."""
        logger.info("Synthesizing clinical guidelines for: %s", disease)

        prompt = (
            f"Disease: {disease}\n\n"
            f"Web search results:\n{search_results}\n\n"
        )
        if patient_context:
            prompt += f"Patient context: {patient_context}\n\n"
        prompt += "Produce a comprehensive clinical guideline document."

        response = self._llm.invoke([
            SystemMessage(content=GUIDELINE_SYNTH_PROMPT),
            HumanMessage(content=prompt),
        ])

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        logger.info("Guidelines synthesized (%d chars)", len(raw))
        return raw

    def _generate_task_json(self, disease: str, patient_context: str = "") -> dict:
        """Generate task.json content for the disease."""
        prompt = f"Disease: {disease}"
        if patient_context:
            prompt += f"\nPatient context: {patient_context}"

        response = self._llm.invoke([
            SystemMessage(content=TASK_GEN_PROMPT),
            HumanMessage(content=prompt),
        ])

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Could not parse task JSON, using defaults")
            return {
                "input": "Medical image of the patient",
                "disease": f"Diagnose potential {disease}",
            }

    def _generate_toolset_json(self, disease: str, guidelines: str) -> list[dict]:
        """Generate toolset.json content for the disease."""
        response = self._llm.invoke([
            SystemMessage(content=TOOLSET_GEN_PROMPT),
            HumanMessage(content=(
                f"Disease: {disease}\n\n"
                f"Clinical guidelines summary:\n{guidelines[:3000]}\n\n"
                "Generate the tools JSON array."
            )),
        ])

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Could not parse toolset JSON, using defaults")
            return [
                {
                    "id": 1,
                    "type": "Vision Language Model (VLM)",
                    "function": "Make qualitative analysis",
                    "input": "Any image, text or multi-modal input",
                    "output": "Qualitative analysis or description of certain features",
                },
                {
                    "id": 2,
                    "type": "coding module",
                    "function": "Write simple code for some indicator computation",
                },
            ]

    def setup(self, disease: str, diseases_dir: str, patient_context: str = "") -> str:
        """Auto-create a complete disease config directory.

        Args:
            disease: Human-readable disease name.
            diseases_dir: Root diseases directory.
            patient_context: Optional patient context for smarter config generation.

        Returns the path to the created disease directory.
        """
        # Normalize disease name for directory
        dir_name = disease.lower().replace(" ", "_").replace("-", "_")
        disease_dir = os.path.join(diseases_dir, dir_name)
        guidelines_dir = os.path.join(disease_dir, "guidelines")
        os.makedirs(guidelines_dir, exist_ok=True)

        logger.info("Setting up disease config for '%s' → %s", disease, disease_dir)

        # 1. Search online for clinical guidelines
        search_results = self._search_guidelines(disease, patient_context)

        # 2. Synthesize guidelines document
        guidelines = self._synthesize_guidelines(disease, search_results, patient_context)
        guidelines_path = os.path.join(guidelines_dir, f"{dir_name}_guidelines.md")
        Path(guidelines_path).write_text(guidelines, encoding="utf-8")
        logger.info("Guidelines saved → %s", guidelines_path)

        # 3. Generate task.json
        task_data = self._generate_task_json(disease, patient_context)
        task_path = os.path.join(disease_dir, "task.json")
        Path(task_path).write_text(
            json.dumps(task_data, indent=4, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("task.json saved → %s", task_path)

        # 4. Generate toolset.json
        toolset_data = self._generate_toolset_json(disease, guidelines)
        toolset_path = os.path.join(disease_dir, "toolset.json")
        Path(toolset_path).write_text(
            json.dumps(toolset_data, indent=4, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("toolset.json saved → %s", toolset_path)

        # 5. Create tools directory
        os.makedirs(os.path.join(disease_dir, "tools"), exist_ok=True)

        logger.info("Disease setup complete for '%s'", disease)
        return disease_dir
