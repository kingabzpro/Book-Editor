from openai import OpenAI
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(5))
def kimi_chat(
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_text: str,
    temperature: float = 0.4,
) -> str:
    client = OpenAI(base_url=base_url, api_key=api_key)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [{"type": "text", "text": user_text}]},
        ],
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""
