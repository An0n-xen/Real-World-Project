from __future__ import annotations
import importlib.util
import re
import textwrap
from pathlib import Path
from types import ModuleType

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from medagent.config import get_settings
from medagent.logger import get_logger
from medagent.schemas import PlanStep, ToolDefinition

logger = get_logger(__name__)

CODING_SYSTEM_PROMPT = """
    You are a medical code generation agent. You write self-contained Python 
    functions for quantitative medical image analysis.

    RULES:
    1. The function signature MUST be exactly: function_name(inputs, save_dir, save_name)
    2. `inputs` is a LIST; elements correspond IN ORDER to the step dependencies.
    3. Each element may be a file path (str) or an in-memory object (numpy array).
    4. Import any needed library INSIDE the function body.
    5. For NON-IMAGE results: write JSON to os.path.join(save_dir, save_name).
    Read existing JSON first, update a unique key (e.g. 'step_N'), write back.
    6. For IMAGE results: save to os.path.join(save_dir, save_name).
    7. Add a brief docstring.
    8. No print statements. No external API calls.

    CRITICAL — IMAGE FILE HANDLING:
    - When an input is a file path to an IMAGE (png/jpg/tif/bmp), ALWAYS load it
    using PIL and convert to numpy:
        from PIL import Image
        import numpy as np
        img = np.array(Image.open(path).convert('L'))   # grayscale
    - NEVER use np.load() on image files. np.load() is ONLY for .npy/.npz files.
    - Segmentation masks are saved as grayscale PNG images where foreground = 255
    and background = 0.

    MEDICAL CONTEXT:
    - Optic disc/cup segmentation masks are binary images (0/255).
    - Cup-to-Disc Ratio (CDR) = cup_area / disc_area  (or vertical CDR from heights).
    - Always produce clinically meaningful computations, not generic stubs.

    Return ONLY the Python function code, no markdown fences.
"""


def _snake(text: str) -> str:
    """Convert *text* to a snake_case identifier."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip()).strip("_").lower()
    return s or "generated_fn"


class CodingAgent:
    """Generate Python functions for computational diagnostic steps."""

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
        logger.info("CodingAgent ready  model=%s", settings.text_llm_model)

    def generate_function(
        self,
        step: PlanStep,
        plan_by_id: dict[int, PlanStep],
        tool_by_id: dict[int, ToolDefinition],
        task_input_desc: str,
        output_file: Path | str,
    ) -> str:
        """Generate a function for *step* and append it to *output_file*.

        Returns the generated function name.
        """
        fn_name = f"{_snake(step.action or step.output_type)}_{step.id}"

        # Build dependency descriptions
        dep_descs = []
        for dep_id in step.input_type:
            if dep_id == 0:
                dep_descs.append(f"raw input ({task_input_desc})")
            else:
                prev = plan_by_id.get(dep_id)
                if prev:
                    dep_descs.append(f"output of step {dep_id} ({prev.action})")

        requirement = (
            f"Implement a Python function: {fn_name}(inputs, save_dir, save_name)\n\n"
            f"Conceptual inputs: {', '.join(dep_descs) or 'raw image'}\n"
            f"Expected output: {step.output_type}\n"
            f"Action description: {step.action}\n\n"
            "Constraints:\n"
            "- Self-contained; add imports inside.\n"
            "- Use os.path.join(save_dir, save_name) for output path.\n"
            "- For JSON outputs, read existing, update key 'step_{id}', write back.\n"
            "- Handle inputs as file paths or numpy arrays gracefully."
        )

        logger.info("Generating code for step %d → %s", step.id, fn_name)

        response = self._llm.invoke([
            SystemMessage(content=CODING_SYSTEM_PROMPT),
            HumanMessage(content=requirement),
        ])

        code = response.content.strip()
        # Strip markdown fences
        if code.startswith("```"):
            code = code.split("\n", 1)[1]
            code = code.rsplit("```", 1)[0]

        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"\n\n# --- Step {step.id}: {step.action} ---\n")
            f.write(code.rstrip() + "\n")

        logger.info("Code written to %s", output_file)
        return fn_name

    def load_generated_module(self, code_path: Path | str) -> ModuleType | None:
        """Dynamically load the generated code file as a Python module."""
        code_path = Path(code_path)
        if not code_path.exists():
            logger.warning("Generated code file not found: %s", code_path)
            return None

        spec = importlib.util.spec_from_file_location("gen_tools", str(code_path))
        if spec is None or spec.loader is None:
            logger.error("Failed to create module spec from %s", code_path)
            return None

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            logger.info("Loaded generated module from %s", code_path)
        except Exception:
            logger.exception("Error loading generated module %s", code_path)
            return None
        return module
