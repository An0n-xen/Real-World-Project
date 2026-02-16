import os
from dotenv import load_dotenv

load_dotenv()

DEEPINFRA_API_TOKEN = os.getenv("DEEPINFRA_API_TOKEN")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.deepinfra.com/v1/openai")

# Model Names
# Using Meta-Llama-3-70b-Instruct as a powerful open-source model available on DeepInfra
REASONING_MODEL = "meta-llama/Meta-Llama-3-70b-Instruct"
# Using a vision-capable model if available, otherwise fallback or separate handling
VISION_MODEL = "llava-hf/llava-1.5-7b-hf" 
