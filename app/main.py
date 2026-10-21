from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

import re
from pathlib import Path

from app.firewall import Configuration, run_pipeline
from app.guards import inspect_input, validate_output_semantically
from app.model_client import (
    generate_answer,
    get_configured_model,
    get_configured_provider,
)

app = FastAPI(
    title="Healthcare LLM Firewall",
    version="0.2.0",
    description=(
        "Research demo using the configured language model and selected "
        "healthcare firewall checks. Not for clinical use."
    ),
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class EvaluateRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    contexts: list[str] = Field(default_factory=list, max_length=20)
    configuration: Configuration = Configuration.A


class EvaluateResponse(BaseModel):
    allowed: bool
    response: str | None
    reason: str
    stages: list[str]
    configuration: Configuration
    demo_mode: bool = True
    security_mode: str = "configured_model_firewall"
    provider: str | None = None
    model: str | None = None
    output_validation: dict[str, object] | None = None
    pipeline_error_type: str | None = None
    pipeline_error_status: int | None = None


def _safe_error_details(error: str | None) -> tuple[str | None, int | None]:
    """Extract only an error category and HTTP status from model-client errors."""
    if not error:
        return None, None

    status_match = re.search(r"API returned HTTP (\d{3})\b", error)
    if status_match:
        return "HTTPStatusError", int(status_match.group(1))

    transport_match = re.search(r"request failed \(([A-Za-z_][A-Za-z0-9_]*)\)", error)
    if transport_match:
        return transport_match.group(1), None

    if "returned empty or incomplete text content" in error:
        return "IncompleteModelResponse", None

    return error.split(":", 1)[0], None


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def demo_page():
    page = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.get("/docs", include_in_schema=False)
def docs_redirect():
    return RedirectResponse(url="/", status_code=307)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(request: EvaluateRequest):
    provider = get_configured_provider()
    model = get_configured_model(provider)
    result = run_pipeline(
        query=request.query,
        contexts=request.contexts,
        configuration=request.configuration,
        generate=generate_answer,
        input_guard=inspect_input,
        output_validator=validate_output_semantically,
    )

    validation = None
    if result.output_validation is not None:
        validation = result.output_validation.to_dict()
        # Return the error class for demo diagnostics without exposing raw
        # provider messages or any request/credential details.
        validation["error_type"], validation["error_status"] = _safe_error_details(
            result.output_validation.error
        )
        validation.pop("error", None)

    pipeline_error_type, pipeline_error_status = _safe_error_details(result.error)

    return EvaluateResponse(
        allowed=result.allowed,
        response=result.response,
        reason=result.reason,
        stages=list(result.stages),
        configuration=request.configuration,
        demo_mode=True,
        provider=provider,
        model=model,
        output_validation=validation,
        pipeline_error_type=pipeline_error_type,
        pipeline_error_status=pipeline_error_status,
    )
