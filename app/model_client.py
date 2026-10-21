import json
import math
import os
from pathlib import Path
import re
import time

import httpx


MAX_RATE_LIMIT_RETRY_SECONDS = 60.0
RATE_LIMIT_RETRIES = 1
SEMANTIC_RISK_CATEGORY_VALUES = (
    "instruction_compromise",
    "dangerous_medication_guidance",
    "clinician_advice_override",
    "discourages_urgent_care",
    "other_unsafe_medical_guidance",
)
PROVIDER_CONFIG = {
    "groq": {
        "api_key_env": "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
        "default_model": "openai/gpt-oss-120b",
        "url": "https://api.groq.com/openai/v1/chat/completions",
    },
    "mistral": {
        "api_key_env": "MISTRAL_API",
        "model_env": "MISTRAL_MODEL",
        "default_model": "mistral-small-latest",
        "url": "https://api.mistral.ai/v1/chat/completions",
    },
    "openrouter": {
        "api_key_env": "OPENROUTER_KEY",
        "model_env": "OPENROUTER_MODEL",
        "default_model": None,
        "url": "https://openrouter.ai/api/v1/chat/completions",
    },
}


def _parse_rate_limit_delay(value: str | None) -> float | None:
    """Parse Groq's numeric Retry-After or reset-token duration header."""
    if not value:
        return None
    value = value.strip().lower()
    try:
        delay = float(value)
    except ValueError:
        match = re.fullmatch(
            r"(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)", value
        )
        if not match:
            return None
        minutes = float(match.group(1) or 0)
        seconds = float(match.group(2))
        delay = minutes * 60 + seconds
    if not math.isfinite(delay) or delay < 0:
        return None
    return delay


def _rate_limit_retry_delay(
    response: httpx.Response,
    *,
    include_token_reset: bool = True,
) -> float | None:
    """Return a bounded wait using Groq's explicit 429 reset headers."""
    delays = [_parse_rate_limit_delay(response.headers.get("retry-after"))]
    if include_token_reset:
        delays.append(
            _parse_rate_limit_delay(
                response.headers.get("x-ratelimit-reset-tokens")
            )
        )
    valid_delays = [delay for delay in delays if delay is not None]
    if not valid_delays:
        return None

    # Retry only after both advertised limits have reset. If that exceeds the
    # local wait cap, leave the 429 as an error for the caller to report.
    delay = max(valid_delays)
    if delay > MAX_RATE_LIMIT_RETRY_SECONDS:
        return None
    return delay


def _rate_limit_error_headers(response: httpx.Response) -> str:
    """Expose only non-secret rate-limit timing/remaining-token headers."""
    names = (
        "retry-after",
        "x-ratelimit-reset-tokens",
        "x-ratelimit-remaining-tokens",
    )
    values = [
        f"{name}={response.headers[name]}"
        for name in names
        if name in response.headers
    ]
    return f" Rate-limit headers: {', '.join(values)}." if values else ""


def _post_with_rate_limit_retry(
    url: str,
    headers: dict,
    payload: dict,
    *,
    provider: str,
):
    """Make a provider request; only Groq uses its bounded 429 retry."""
    retries = RATE_LIMIT_RETRIES if provider == "groq" else 0
    for attempt in range(retries + 1):
        response = httpx.post(
            url,
            headers=headers,
            json=payload,
            timeout=45.0,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429 or attempt >= retries:
                raise
            delay = _rate_limit_retry_delay(
                exc.response,
                include_token_reset=(provider == "groq"),
            )
            if delay is None:
                raise
            time.sleep(delay)
        else:
            return response
    raise RuntimeError(f"{provider.title()} rate-limit retry loop ended unexpectedly.")


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
        if key.strip() in {
            "GROQ_API_KEY",
            "MISTRAL_API",
            "OPENROUTER_KEY",
        }:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")
        else:
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_configured_provider() -> str:
    """Return the selected OpenAI-compatible inference provider."""
    load_local_env()
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    if provider not in PROVIDER_CONFIG:
        choices = ", ".join(sorted(PROVIDER_CONFIG))
        raise RuntimeError(f"LLM_PROVIDER must be one of: {choices}.")
    return provider


def get_configured_model(provider: str | None = None) -> str:
    """Return the configured model for the selected provider."""
    load_local_env()
    provider = provider or get_configured_provider()
    if provider not in PROVIDER_CONFIG:
        choices = ", ".join(sorted(PROVIDER_CONFIG))
        raise RuntimeError(f"LLM_PROVIDER must be one of: {choices}.")
    settings = PROVIDER_CONFIG[provider]
    model = os.getenv(settings["model_env"], settings["default_model"])
    if not model:
        raise RuntimeError(
            f"{settings['model_env']} is required for the {provider} provider."
        )
    return model


def _generate_chat_completion(
    system_prompt: str,
    user_prompt: str,
    *,
    response_format: dict | None = None,
    max_tokens: int = 512,
    reasoning_effort: str | None = None,
    reasoning: dict | None = None,
) -> tuple[str, str]:
    """Use the existing configured model connection for a completion."""
    load_local_env()
    provider = get_configured_provider()
    settings = PROVIDER_CONFIG[provider]
    api_key = os.getenv(settings["api_key_env"])
    if not api_key:
        raise RuntimeError(
            f"{settings['api_key_env']} is missing. Configure it in your local .env file."
        )

    model = get_configured_model(provider)
    url = settings["url"]
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
    if reasoning_effort is not None:
        payload["reasoning_effort"] = reasoning_effort
    if reasoning is not None:
        payload["reasoning"] = reasoning

    try:
        response = _post_with_rate_limit_retry(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            payload=payload,
            provider=provider,
        )
        data = response.json()

    except httpx.HTTPStatusError as exc:
        # Include Groq's error message to help identify the exact issue.
        try:
            error_data = exc.response.json()
            error_message = (
                error_data.get("error", {}).get("message")
                or error_data.get("message")
                or "No provider error message returned."
            )
        except (ValueError, AttributeError):
            error_message = f"{provider.title()} returned a non-JSON error response."

        raise RuntimeError(
            f"{provider.title()} API returned HTTP {exc.response.status_code}: "
            f"{error_message}"
            + (
                _rate_limit_error_headers(exc.response)
                if provider == "groq"
                else ""
            )
        ) from None

    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"{provider.title()} request failed ({type(exc).__name__}): {exc}"
        ) from exc

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError(
            f"{provider.title()} returned no response choice; check the provider response."
        )

    choice = choices[0]
    message = choice.get("message", {})
    answer = message.get("content", "")
    if not isinstance(answer, str):
        answer = ""
    answer = answer.strip()

    if not answer or choice.get("finish_reason") == "length":
        usage = data.get("usage", {})
        raise RuntimeError(
            f"{provider.title()} returned empty or incomplete text content. "
            f"finish_reason={choice.get('finish_reason')!r}; "
            f"message_fields={list(message.keys())}; "
            f"usage={usage!r}"
        )

    response_model = data.get("model", model)
    if not isinstance(response_model, str) or not response_model:
        response_model = model
    return answer, response_model


def generate_answer(query: str, contexts: list[str]) -> str:
    """Generate a response through the configured model connection."""
    provider = get_configured_provider()
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
        max_tokens=2048 if provider == "openrouter" else 1024,
        reasoning_effort=(
            "low" if provider == "groq" else None
        ),
        reasoning=(
            {"effort": "low", "summary": "concise"}
            if provider == "openrouter"
            else None
        ),
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
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "healthcare_output_validation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "decision": {
                            "type": "string",
                            "enum": ["allow", "block"],
                        },
                        "risk_categories": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": list(SEMANTIC_RISK_CATEGORY_VALUES),
                            },
                        },
                        "reason": {"type": "string"},
                    },
                    "required": [
                        "decision",
                        "risk_categories",
                        "reason",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        # OpenRouter reasoning models can spend the full completion budget
        # before emitting the required JSON. Keep reasoning low and reserve
        # enough completion space for the structured decision.
        max_tokens=512,
        reasoning=(
            {"effort": "low", "summary": "concise"}
            if get_configured_provider() == "openrouter"
            else None
        ),
    )
