from openai import AsyncOpenAI
from src.config import config

def get_client() -> AsyncOpenAI:
    """Returns a pre-configured AsyncOpenAI client for LM Studio."""
    return AsyncOpenAI(
        base_url=config.lm_studio_base_url,
        api_key="lm-studio"
    )
