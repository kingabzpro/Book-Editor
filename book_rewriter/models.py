"""Nebius LLM client — OpenAI-compatible API."""
from openai import OpenAI
from tenacity import retry, wait_exponential, stop_after_attempt


@retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(4))
def chat(
    api_key: str,
    base_url: str,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.7,
) -> str:
    """Call any Nebius-hosted model via the OpenAI-compatible API."""
    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""
