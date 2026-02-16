from langchain_openai import ChatOpenAI
from src.config import DEEPINFRA_API_TOKEN, OPENAI_API_BASE, REASONING_MODEL, VISION_MODEL

def get_reasoning_llm():
    """
    Returns the LLM for reasoning tasks (Planner, Diagnostician logic).
    """
    if not DEEPINFRA_API_TOKEN:
        raise ValueError("DEEPINFRA_API_TOKEN not found in environment variables.")

    return ChatOpenAI(
        api_key=DEEPINFRA_API_TOKEN,
        base_url=OPENAI_API_BASE,
        model=REASONING_MODEL,
        temperature=0.1, # Low temperature for more deterministic/factual reasoning
    )

def get_vision_llm():
    """
    Returns the LLM for visual tasks.
    If the provider/model doesn't support images via standard API, this might need 
    a custom adapter. For DeepInfra, we'll try the standard ChatOpenAI interface 
    pointing to a vision model.
    """
    if not DEEPINFRA_API_TOKEN:
        raise ValueError("DEEPINFRA_API_TOKEN not found in environment variables.")

    return ChatOpenAI(
        api_key=DEEPINFRA_API_TOKEN,
        base_url=OPENAI_API_BASE,
        model=VISION_MODEL,
        temperature=0.1,
    )
