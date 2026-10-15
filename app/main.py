from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.firewall import Configuration, run_pipeline
from app.guards import inspect_input, validate_output

app = FastAPI(
    title="Healthcare LLM Firewall",
    version="0.2.0",
    description="Research prototype with rule-based baseline controls.",
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
    demo_mode: bool = True
    security_mode: str = "rule_based_baseline"


def placeholder_generator(query: str, contexts: list[str]) -> str:
    return (
        "DEVELOPMENT PLACEHOLDER: no medical answer was generated. "
        "Replace this generator with the selected inference model."
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "security_mode": "rule_based_baseline",
        "real_model_connected": False,
    }


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(request: EvaluateRequest):
    result = run_pipeline(
        query=request.query,
        contexts=request.contexts,
        configuration=request.configuration,
        generate=placeholder_generator,
        input_guard=inspect_input,
        output_validator=validate_output,
    )

    return EvaluateResponse(
        allowed=result.allowed,
        response=result.response,
        reason=result.reason,
        stages=list(result.stages),
        demo_mode=True,
    )
