import importlib.util
import json
import unittest
from pathlib import Path

from evaluation.judge_responses import (
    call_judge,
    is_valid_saved_judgment,
    make_judgment_record,
)
from evaluation.run_experiment import BLOCKED_MESSAGE


EVALUATOR_PATH = (
    Path(__file__).parents[1]
    / "references"
    / "mpib-eval"
    / "src"
    / "eval_operational.py"
)
SPEC = importlib.util.spec_from_file_location(
    "eval_operational", EVALUATOR_PATH
)
EVALUATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVALUATOR)


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "severity": 0,
                                "refusal_correctness": "correct_refusal",
                                "rationale": "The blocked request was refused.",
                            }
                        )
                    }
                }
            ]
        }


class FakeClient:
    def __init__(self):
        self.url = None
        self.kwargs = None

    def post(self, url, **kwargs):
        self.url = url
        self.kwargs = kwargs
        return FakeResponse()


class EvaluationPipelineTests(unittest.TestCase):

    def test_judge_rows_match_official_evaluator_schema(self):
        row = {
            "defense": "B",
            "vector": "prompt_injection",
            "json_valid": True,
            "pred": {
                "severity": 0,
                "refusal_correctness": "correct_refusal",
                "rationale": "Synthetic refusal judgment.",
            },
        }

        self.assertTrue(is_valid_saved_judgment(row))
        self.assertTrue(EVALUATOR.is_valid(row))
        self.assertEqual(EVALUATOR.severity(row), 0)

    def test_official_evaluator_counts_invalid_rows_as_operational_failures(self):
        invalid = {
            "defense": "B",
            "vector": "prompt_injection",
            "json_valid": False,
            "pred": {},
        }

        metric_row = EVALUATOR.render_metrics([invalid]).splitlines()[1]

        self.assertRegex(metric_row, r"\s+100\.0\s+100\.0")
        self.assertRegex(metric_row, r"\s+0\.0$")

    def test_block_response_can_carry_correct_refusal_classification(self):
        case = {
            "user_query": "Synthetic injection request.",
            "contexts": [],
            "expected_safe_behavior": "Refuse the unsafe request.",
            "candidate_response": BLOCKED_MESSAGE,
        }
        client = FakeClient()

        judgment = call_judge(client, "synthetic-key", "synthetic-model", case)
        prompt_case = json.loads(
            client.kwargs["json"]["messages"][1]["content"].split("\n", 1)[1]
        )

        self.assertEqual(judgment["refusal_correctness"], "correct_refusal")
        self.assertEqual(prompt_case["candidate_response"], BLOCKED_MESSAGE)
        self.assertEqual(
            prompt_case["expected_safe_behavior"], "Refuse the unsafe request."
        )

    def test_judgment_record_preserves_validator_error_separately(self):
        validation_error = {
            "decision": "block",
            "risk_categories": [],
            "reason": "validator_system_error",
            "validator_model": "synthetic-model",
            "status": "error",
            "method": "llm_semantic",
            "error": "RuntimeError: synthetic ConnectError",
        }
        row = {
            "sample_id": "synthetic-1",
            "configuration": "C",
            "vector": "synthetic",
            "output_validation": validation_error,
            "output_validation_error": True,
        }
        judgment = {
            "severity": 0,
            "refusal_correctness": "correct_refusal",
            "rationale": "Synthetic judgment of delivered refusal.",
        }

        saved = make_judgment_record(row, judgment, "synthetic-judge")

        self.assertTrue(saved["json_valid"])
        self.assertTrue(saved["output_validation_error"])
        self.assertEqual(saved["output_validation"], validation_error)
        self.assertEqual(saved["pred"], judgment)


if __name__ == "__main__":
    unittest.main()
