from dataclasses import dataclass
from enum import Enum
from typing import Callable


class Configuration(str, Enum):
    A = "A"  # No external firewall
    B = "B"  # Input/context defense
    C = "C"  # Output validation
    D = "D"  # Combined defense


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class ValidationResult:
    allowed: bool
    reason: str
    risk_categories: tuple[str, ...] = ()
    validator_model: str | None = None
    status: str = "success"
    method: str = "deterministic_baseline"
    error: str | None = None

    @property
    def decision(self) -> str:
        return "allow" if self.allowed else "block"

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "risk_categories": list(self.risk_categories),
            "reason": self.reason,
            "validator_model": self.validator_model,
            "status": self.status,
            "method": self.method,
            "error": self.error,
        }


@dataclass(frozen=True)
class PipelineResult:
    allowed: bool
    response: str | None
    reason: str
    stages: tuple[str, ...]
    output_validation: ValidationResult | None = None
    error: str | None = None


InputGuard = Callable[[str, list[str]], GuardResult]
Generator = Callable[[str, list[str]], str]
OutputValidator = Callable[[str, str, list[str]], ValidationResult]


def run_pipeline(
    query: str,
    contexts: list[str],
    configuration: Configuration,
    generate: Generator,
    input_guard: InputGuard | None = None,
    output_validator: OutputValidator | None = None,
) -> PipelineResult:
    """Run one configuration with fail-closed enforcement."""

    stages: list[str] = []

    if not isinstance(query, str) or not query.strip():
        return PipelineResult(False, None, "invalid_query", ("input",))

    if not isinstance(contexts, list) or not all(
        isinstance(context, str) for context in contexts
    ):
        return PipelineResult(False, None, "invalid_contexts", ("input",))

    use_input_guard = configuration in (Configuration.B, Configuration.D)
    use_output_validator = configuration in (Configuration.C, Configuration.D)

    if use_input_guard:
        stages.append("input_guard")

        if input_guard is None:
            return PipelineResult(
                False, None, "input_guard_not_configured", tuple(stages)
            )

        try:
            decision = input_guard(query, contexts)
        except Exception:
            return PipelineResult(
                False, None, "input_guard_error", tuple(stages)
            )

        if not isinstance(decision, GuardResult) or decision.allowed is not True:
            reason = (
                decision.reason
                if isinstance(decision, GuardResult)
                else "invalid_input_guard_result"
            )
            return PipelineResult(False, None, reason, tuple(stages))

    stages.append("generation")

    try:
        response = generate(query, contexts)
    except Exception as exc:
        return PipelineResult(
            False,
            None,
            "generation_error",
            tuple(stages),
            error=f"{type(exc).__name__}: {exc}",
        )

    if not isinstance(response, str) or not response.strip():
        return PipelineResult(
            False, None, "invalid_generation_output", tuple(stages)
        )

    if use_output_validator:
        stages.append("output_validator")

        if output_validator is None:
            return PipelineResult(
                False, None, "output_validator_not_configured", tuple(stages)
            )

        try:
            decision = output_validator(query, response, contexts)
        except Exception as exc:
            validation_error = ValidationResult(
                False,
                "Output validation failed; response blocked.",
                status="error",
                method="output_validator",
                error=f"{type(exc).__name__}: {exc}",
            )
            return PipelineResult(
                False,
                None,
                "output_validator_error",
                tuple(stages),
                validation_error,
            )

        if not isinstance(decision, ValidationResult):
            validation_error = ValidationResult(
                False,
                "Output validator returned an invalid result; response blocked.",
                status="error",
                method="output_validator",
                error="invalid_output_validator_result",
            )
            return PipelineResult(
                False,
                None,
                "output_validator_error",
                tuple(stages),
                validation_error,
            )

        if decision.status != "success":
            return PipelineResult(
                False,
                None,
                "output_validator_error",
                tuple(stages),
                decision,
            )

        if decision.allowed is not True:
            return PipelineResult(
                False,
                None,
                decision.reason,
                tuple(stages),
                decision,
            )

        output_validation = decision
    else:
        output_validation = None

    stages.append("released")
    return PipelineResult(
        True,
        response,
        "allowed",
        tuple(stages),
        output_validation,
    )
