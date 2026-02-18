from __future__ import annotations
import base64
import json
import os
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from medagent.config import get_settings
from medagent.logger import get_logger

logger = get_logger(__name__)

ANALYZER_SYSTEM_PROMPT = """
        You are a clinical image analysis specialist. You carefully examine 
        medical images and provide detailed, evidence-based qualitative assessments.

        RULES:
        1. Describe what you observe objectively.
        2. Note any abnormalities or notable findings.
        3. Reference specific visual features (color, shape, size, location).
        4. Indicate your confidence level for each observation.
        5. Be precise — avoid vague or overly general statements.

        Output your analysis as a JSON object with these keys:
        - "observation": detailed description of findings
        - "abnormality_detected": true/false
        - "confidence": float between 0 and 1
        - "reasoning": brief explanation of your assessment
"""


def _encode_image(image_path: str) -> str:
    """Read an image file and return its base64 encoding."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _image_media_type(path: str) -> str:
    """Infer MIME type from file extension."""
    ext = Path(path).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }.get(ext, "image/png")


class AnalyzerAgent:
    """Perform qualitative analysis of medical images using a multi-modal VLM."""

    def __init__(self) -> None:
        settings = get_settings()
        self._llm = ChatOpenAI(
            model=settings.primary_vlm_model,
            api_key=settings.deepinfra_api_key,
            base_url=settings.deepinfra_base_url,
            temperature=0,
            max_tokens=2048,
            model_kwargs={"seed": 42},
        )
        logger.info("AnalyzerAgent ready  model=%s", settings.primary_vlm_model)

    def analyze(
        self,
        prompt: str,
        image_paths: list[str] | None = None,
        text_context: list[str] | None = None,
    ) -> dict:
        """Run qualitative analysis on the given images with *prompt*.

        Returns parsed JSON analysis result.
        """
        # Build message content array (text + images)
        content: list[dict] = []

        # Add text context if provided
        full_prompt = prompt
        if text_context:
            full_prompt += "\n\nAdditional context:\n" + "\n".join(text_context)

        content.append({"type": "text", "text": full_prompt})

        # Add images as base64
        for img_path in image_paths or []:
            if not os.path.exists(img_path):
                logger.warning("Image not found: %s", img_path)
                continue

            b64 = _encode_image(img_path)
            media_type = _image_media_type(img_path)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{b64}",
                    },
                }
            )
            logger.debug("Attached image: %s", img_path)

        logger.info(
            "Running qualitative analysis  images=%d  prompt_len=%d",
            len(image_paths or []),
            len(full_prompt),
        )

        response = self._llm.invoke([
            SystemMessage(content=ANALYZER_SYSTEM_PROMPT),
            HumanMessage(content=content),
        ])

        raw = response.content.strip()
        # Strip markdown fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Could not parse VLM response as JSON, wrapping as text")
            result = {
                "observation": raw,
                "abnormality_detected": False,
                "confidence": 0.0,
                "reasoning": "Unparsed VLM response",
            }

        logger.info(
            "Analysis complete  abnormal=%s  confidence=%.2f",
            result.get("abnormality_detected", "?"),
            result.get("confidence", 0),
        )
        return result

    def analyze_and_save(
        self,
        prompt: str,
        image_paths: list[str] | None,
        output_file: str | Path,
        field: str = "analysis",
        text_context: list[str] | None = None,
    ) -> dict:
        """Run analysis and persist the result into a JSON file under *field*."""
        result = self.analyze(prompt, image_paths, text_context)

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
        logger.info("Result saved → %s [%s]", output_file, field)
        return result
