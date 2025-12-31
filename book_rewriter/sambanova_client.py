"""
SambaNova API client for multi-turn rewrite pipeline.

Uses the SambaNova SDK for gpt-oss-120b model (grammar baseline turn).
"""

from typing import Dict, List

from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from sambanova import SambaNova

    SAMBANOVA_AVAILABLE = True
except ImportError:
    SAMBANOVA_AVAILABLE = False


@retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(5))
def sambanova_chat(
    api_key: str,
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    top_p: float = 0.1,
) -> str:
    """
    Send a chat completion request to SambaNova API.

    Args:
        api_key: SambaNova API key
        base_url: API base URL (e.g., "https://api.sambanova.ai/v1")
        model: Model name (e.g., "gpt-oss-120b")
        messages: List of message dicts with 'role' and 'content'
        temperature: Sampling temperature (0.0 to 1.0)
        top_p: Nucleus sampling parameter

    Returns:
        The assistant's response text
    """
    if not SAMBANOVA_AVAILABLE:
        raise ImportError(
            "SambaNova SDK is not installed. Install with: pip install sambanova-sdk"
        )

    client = SambaNova(api_key=api_key, base_url=base_url)

    response = client.chat.completions.create(
        model=model, messages=messages, temperature=temperature, top_p=top_p
    )

    return response.choices[0].message.content or ""


@retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(5))
def sambanova_chat_simple(
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_text: str,
    temperature: float = 0.1,
    top_p: float = 0.1,
) -> str:
    """
    Simplified interface for SambaNova chat with system and user messages.

    Args:
        api_key: SambaNova API key
        base_url: API base URL
        model: Model name
        system_prompt: System prompt content
        user_text: User message content
        temperature: Sampling temperature
        top_p: Nucleus sampling parameter

    Returns:
        The assistant's response text
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    return sambanova_chat(
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
    )
