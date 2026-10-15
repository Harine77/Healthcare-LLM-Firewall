import json
import unittest
from unittest.mock import patch

from app.firewall import Configuration, run_pipeline
from app.guards import (
    inspect_input,
    validate_output_semantically,
)


class SemanticValidatorTests(unittest.TestCase):

    def test_safe_medical_answer_uses_configured_model_and_allows(self):
        with (
            patch(
                "app.guards.get_configured_model",
                return_value="configured-model",
            ),
            patch(
                "app.guards.generate_structured_response",
                return_value=(
                    json.dumps(
                        {
                            "decision": "allow",
                            "risk_categories": [],
                            "reason": "No clearly unsafe guidance identified.",
                        }
                    ),
                    "configured-model",
                ),
            ) as request,
        ):
            result = validate_output_semantically(
                "What general information is available about sleep?",
                "Synthetic general information about sleep.",
                ["Synthetic reference context."],
            )

        self.assertTrue(result.allowed)
        self.assertEqual(result.decision, "allow")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.method, "llm_semantic")
        self.assertEqual(result.validator_model, "configured-model")
        self.assertIn(
            "Synthetic general information about sleep.",
            request.call_args.args[1],
        )

    def test_semantic_risk_returns_structured_block(self):
        with (
            patch(
                "app.guards.get_configured_model",
                return_value="configured-model",
            ),
            patch(
                "app.guards.generate_structured_response",
                return_value=(
                    json.dumps(
                        {
                            "decision": "block",
                            "risk_categories": [
                                "dangerous_medication_guidance"
                            ],
                            "reason": "The answer directs an unsafe dose change.",
                        }
                    ),
                    "configured-model",
                ),
            ),
        ):
            result = validate_output_semantically(
                "Synthetic question.",
                "Synthetic answer with an unrecognized medication directive.",
                [],
            )

        self.assertFalse(result.allowed)
        self.assertEqual(result.decision, "block")
        self.assertEqual(
            result.risk_categories,
            ("dangerous_medication_guidance",),
        )
        self.assertEqual(result.status, "success")

    def test_malformed_semantic_response_is_an_error_not_an_allow(self):
        with (
            patch(
                "app.guards.get_configured_model",
                return_value="configured-model",
            ),
            patch(
                "app.guards.generate_structured_response",
                return_value=("not-json", "configured-model"),
            ),
        ):
            result = validate_output_semantically(
                "Synthetic question.", "Synthetic answer.", []
            )

        self.assertFalse(result.allowed)
        self.assertEqual(result.decision, "block")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "validator_system_error")
        self.assertEqual(result.risk_categories, ())
        self.assertIn("JSONDecodeError", result.error)

    def test_validator_errors_fail_closed_in_c_and_d(self):
        with (
            patch(
                "app.guards.get_configured_model",
                return_value="configured-model",
            ),
            patch(
                "app.guards.generate_structured_response",
                side_effect=RuntimeError("synthetic HTTP 503"),
            ),
        ):
            for config in (Configuration.C, Configuration.D):
                with self.subTest(config=config):
                    result = run_pipeline(
                        query="Synthetic question.",
                        contexts=[],
                        configuration=config,
                        generate=lambda q, c: "Synthetic candidate answer.",
                        input_guard=inspect_input,
                        output_validator=validate_output_semantically,
                    )

                    self.assertFalse(result.allowed)
                    self.assertIsNone(result.response)
                    self.assertEqual(result.reason, "output_validator_error")
                    self.assertEqual(result.output_validation.decision, "block")
                    self.assertEqual(result.output_validation.status, "error")
                    self.assertEqual(
                        result.output_validation.validator_model,
                        "configured-model",
                    )
                    self.assertEqual(
                        result.output_validation.risk_categories, ()
                    )
                    self.assertIn(
                        "synthetic HTTP 503",
                        result.output_validation.error,
                    )

    def test_deterministic_baseline_blocks_without_claiming_llm_validation(self):
        with patch("app.guards.generate_structured_response") as request:
            result = validate_output_semantically(
                "Synthetic question.",
                "You should stop taking your prescribed medication.",
                [],
            )

        self.assertFalse(result.allowed)
        self.assertEqual(result.method, "deterministic_baseline")
        self.assertEqual(result.status, "success")
        self.assertEqual(
            result.risk_categories,
            ("dangerous_medication_guidance",),
        )
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
