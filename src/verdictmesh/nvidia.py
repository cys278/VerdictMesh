"""Optional NVIDIA hosted inference adapter for cookbook examples."""
import os
from functools import lru_cache
from openai import OpenAI

MODEL = os.getenv("NVIDIA_MODEL", "z-ai/glm-5.3-flash")

@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    key = os.getenv("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("Set NVIDIA_API_KEY before running this demo.")
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=key,
        timeout=180.0,
        max_retries=0,
    )

def generate(prompt: str, *, model: str = MODEL, max_tokens: int = 2048) -> str:
    response = get_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        reasoning_effort="low",
        max_tokens=max_tokens,
        temperature=0.1,
    )
    text = response.choices[0].message.content
    if not text:
        raise RuntimeError(
            f"NVIDIA returned no answer (finish_reason={response.choices[0].finish_reason})."
        )
    return text
