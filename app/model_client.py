import json
import os
from pathlib import Path

import httpx


def load_local_env():
    """Load simple KEY=value entries without overriding existing variables."""
    env_path = Path(".env")
    if not env_path.is_file():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "GROQ_API_KEY":
            os.environ[key.strip()] = value.strip().strip('"').strip("'")
        else:
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_configured_model() -> str:
    """Return the model selected by the existing local configuration."""
    load_local_env()
    return os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def _generate_chat_completion(
    system_prompt: str,
    user_prompt: str,
    *,
    response_format: dict | None = None,
    max_tokens: int = 512,
) -> tuple[str, str]:
    """Use the existing configured model connection for a completion."""
    load_local_env()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Configure it in your local .env file."
        )

    model = get_configured_model()
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=45.0,
        )
        response.raise_for_status()
        data = response.json()

    except httpx.HTTPStatusError as exc:
        # Include Groq's error message to help identify the exact issue.
        try:
            error_data = exc.response.json()
            error_message = error_data.get("error", {}).get(
                "message", "No provider error message returned."
            )
        except (ValueError, AttributeError):
            error_message = "Groq returned a non-JSON error response."

        raise RuntimeError(
            f"Groq API returned HTTP {exc.response.status_code}: "
            f"{error_message}"
        ) from None

    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Groq request failed ({type(exc).__name__})."
        ) from None

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError(
            "Groq returned no response choice; check the provider response."
        )

    answer = choices[0].get("message", {}).get("content", "")
    if not isinstance(answer, str):
        answer = ""
    answer = answer.strip()

    if not answer:
        raise RuntimeError("Groq returned an empty text response.")

    response_model = data.get("model", model)
    if not isinstance(response_model, str) or not response_model:
        response_model = model
    return answer, response_model


def generate_answer(query: str, contexts: list[str]) -> str:
    """Generate a response through the configured model connection."""
    context_text = "\n\n".join(contexts)
    prompt = (
        f"Question:\n{query}\n\n"
        f"Additional context:\n{context_text}\n"
        "Provide concise general health information. Do not claim to be "
        "a clinician or diagnose the user. For urgent symptoms, advise "
        "seeking appropriate urgent medical care."
    )
    answer, _ = _generate_chat_completion(
        "You are a general healthcare information assistant. "
        "Give cautious, general information and acknowledge "
        "uncertainty when appropriate.",
        prompt,
    )
    return answer


def generate_structured_response(
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, str]:
    """Request a JSON response using the same provider, key, and model."""
    return _generate_chat_completion(
        system_prompt,
        user_prompt,
        response_format={"type": "json_object"},
        max_tokens=768,
    )
