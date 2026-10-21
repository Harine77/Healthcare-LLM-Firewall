import json
import os
import unittest
from unittest.mock import patch

import httpx

from app.model_client import (
    _generate_chat_completion,
    generate_answer,
    generate_structured_response,
)


class ModelClientTests(unittest.TestCase):

    def setUp(self):
        provider_env = patch.dict(os.environ, {"LLM_PROVIDER": "groq"})
        provider_env.start()
        self.addCleanup(provider_env.stop)

    def test_generation_request_uses_1024_tokens_and_low_reasoning(self):
        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "model": "synthetic-model",
                    "choices": [
                        {
                            "message": {"content": "Synthetic answer."},
                            "finish_reason": "stop",
                        }
                    ],
                }

        with (
            patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}),
            patch("app.model_client.load_local_env"),
            patch(
                "app.model_client.get_configured_model",
                return_value="synthetic-model",
            ),
            patch("app.model_client.httpx.post", return_value=FakeResponse()) as post,
        ):
            answer = generate_answer("Synthetic question?", [])

        self.assertEqual(answer, "Synthetic answer.")
        self.assertEqual(post.call_args.kwargs["json"]["max_tokens"], 1024)
        self.assertEqual(
            post.call_args.kwargs["json"]["reasoning_effort"], "low"
        )

    def test_mistral_generation_uses_configured_key_endpoint_and_model(self):
        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "model": "mistral-test-model",
                    "choices": [
                        {
                            "message": {"content": "Synthetic Mistral answer."},
                            "finish_reason": "stop",
                        }
                    ],
                }

        with (
            patch.dict(
                os.environ,
                {
                    "LLM_PROVIDER": "mistral",
                    "MISTRAL_API": "synthetic-mistral-key",
                    "MISTRAL_MODEL": "mistral-test-model",
                },
                clear=True,
            ),
            patch("app.model_client.load_local_env"),
            patch("app.model_client.httpx.post", return_value=FakeResponse()) as post,
        ):
            answer = generate_answer("Synthetic question?", [])

        self.assertEqual(answer, "Synthetic Mistral answer.")
        self.assertEqual(
            post.call_args.args[0],
            "https://api.mistral.ai/v1/chat/completions",
        )
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer synthetic-mistral-key",
        )
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "mistral-test-model")
        self.assertNotIn("reasoning_effort", payload)

    def test_mistral_semantic_request_uses_mistral_endpoint_and_schema(self):
        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "model": "mistral-small-latest",
                    "choices": [
                        {
                            "message": {
                                "content": '{"decision":"allow",'
                                '"risk_categories":[],"reason":"safe"}'
                            },
                            "finish_reason": "stop",
                        }
                    ],
                }

        with (
            patch.dict(
                os.environ,
                {
                    "LLM_PROVIDER": "mistral",
                    "MISTRAL_API": "synthetic-mistral-key",
                },
                clear=True,
            ),
            patch("app.model_client.load_local_env"),
            patch("app.model_client.httpx.post", return_value=FakeResponse()) as post,
        ):
            raw, model = generate_structured_response("system", "user")

        self.assertEqual(model, "mistral-small-latest")
        self.assertEqual(json.loads(raw)["decision"], "allow")
        self.assertEqual(
            post.call_args.args[0],
            "https://api.mistral.ai/v1/chat/completions",
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["response_format"]["type"],
            "json_schema",
        )

    def test_openrouter_uses_configured_key_endpoint_and_model(self):
        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "model": "minimax/minimax-m3.1-flash:free",
                    "choices": [
                        {
                            "message": {"content": "Synthetic answer."},
                            "finish_reason": "stop",
                        }
                    ],
                }

        with (
            patch.dict(
                os.environ,
                {
                    "LLM_PROVIDER": "openrouter",
                    "OPENROUTER_KEY": "synthetic-openrouter-key",
                    "OPENROUTER_MODEL": "minimax/minimax-m3.1-flash:free",
                },
                clear=True,
            ),
            patch("app.model_client.load_local_env"),
            patch("app.model_client.httpx.post", return_value=FakeResponse()) as post,
        ):
            answer = generate_answer("Synthetic question?", [])

        self.assertEqual(answer, "Synthetic answer.")
        self.assertEqual(
            post.call_args.args[0],
            "https://openrouter.ai/api/v1/chat/completions",
        )
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer synthetic-openrouter-key",
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["model"],
            "minimax/minimax-m3.1-flash:free",
        )
        self.assertEqual(post.call_args.kwargs["json"]["max_tokens"], 2048)
        self.assertEqual(
            post.call_args.kwargs["json"]["reasoning"],
            {"effort": "low", "summary": "concise"},
        )

    def test_openrouter_requires_explicit_model_selection(self):
        with (
            patch.dict(
                os.environ,
                {
                    "LLM_PROVIDER": "openrouter",
                    "OPENROUTER_KEY": "synthetic-openrouter-key",
                },
                clear=True,
            ),
            patch("app.model_client.load_local_env"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "OPENROUTER_MODEL is required for the openrouter provider",
            ):
                _generate_chat_completion("system", "user")

    def test_empty_generated_content_remains_an_error(self):
        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "model": "synthetic-model",
                    "choices": [
                        {
                            "message": {"content": "", "reasoning": "..."},
                            "finish_reason": "length",
                        }
                    ],
                    "usage": {"completion_tokens": 1024},
                }

        with (
            patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}),
            patch("app.model_client.load_local_env"),
            patch(
                "app.model_client.get_configured_model",
                return_value="synthetic-model",
            ),
            patch("app.model_client.httpx.post", return_value=FakeResponse()),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"Groq returned empty or incomplete text content.*finish_reason='length'.*completion_tokens",
            ):
                generate_answer("Synthetic question?", [])

    def test_truncated_nonempty_generation_remains_an_error(self):
        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "model": "synthetic-model",
                    "choices": [
                        {
                            "message": {"content": "Partial answer"},
                            "finish_reason": "length",
                        }
                    ],
                    "usage": {"completion_tokens": 1024},
                }

        with (
            patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}),
            patch("app.model_client.load_local_env"),
            patch(
                "app.model_client.get_configured_model",
                return_value="synthetic-model",
            ),
            patch("app.model_client.httpx.post", return_value=FakeResponse()),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Groq returned empty or incomplete text content",
            ):
                generate_answer("Synthetic question?", [])

    def test_transport_error_detail_is_preserved_without_credentials(self):
        transport_error = httpx.ConnectError("synthetic connection reset")
        with (
            patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}),
            patch("app.model_client.load_local_env"),
            patch(
                "app.model_client.get_configured_model",
                return_value="synthetic-model",
            ),
            patch("app.model_client.httpx.post", side_effect=transport_error),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"Groq request failed \(ConnectError\): synthetic connection reset",
            ) as raised:
                _generate_chat_completion("system", "user")

        self.assertIs(raised.exception.__cause__, transport_error)

    def test_semantic_request_uses_bounded_completion_budget(self):
        with patch(
            "app.model_client._generate_chat_completion",
            return_value=("{}", "synthetic-model"),
        ) as request, patch(
            "app.model_client.get_configured_provider",
            return_value="openrouter",
        ):
            generate_structured_response("system", "user")

        self.assertEqual(request.call_args.kwargs["max_tokens"], 512)
        self.assertEqual(
            request.call_args.kwargs["reasoning"],
            {"effort": "low", "summary": "concise"},
        )
        response_format = request.call_args.kwargs["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        schema = response_format["json_schema"]
        self.assertTrue(schema["strict"])
        self.assertEqual(
            schema["schema"]["required"],
            ["decision", "risk_categories", "reason"],
        )
        self.assertFalse(schema["schema"]["additionalProperties"])
        self.assertEqual(
            schema["schema"]["properties"]["risk_categories"]["items"]["enum"],
            [
                "instruction_compromise",
                "dangerous_medication_guidance",
                "clinician_advice_override",
                "discourages_urgent_care",
                "other_unsafe_medical_guidance",
            ],
        )

    @staticmethod
    def _response(status_code, *, headers=None, payload=None):
        return httpx.Response(
            status_code,
            headers=headers,
            json=payload or {},
            request=httpx.Request("POST", "https://api.groq.com/test"),
        )

    def test_rate_limit_waits_from_header_and_retries_once(self):
        rate_limited = self._response(
            429,
            headers={"x-ratelimit-reset-tokens": "1.25s"},
            payload={"error": {"message": "rate limited"}},
        )
        success = self._response(
            200,
            payload={
                "model": "synthetic-model",
                "choices": [{"message": {"content": "answer"}}],
            },
        )
        with (
            patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}),
            patch("app.model_client.load_local_env"),
            patch(
                "app.model_client.get_configured_model",
                return_value="synthetic-model",
            ),
            patch(
                "app.model_client.httpx.post",
                side_effect=[rate_limited, success],
            ) as post,
            patch("app.model_client.time.sleep") as sleep,
        ):
            answer, _ = _generate_chat_completion("system", "user")

        self.assertEqual(answer, "answer")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(1.25)

    def test_rate_limit_waits_for_longer_reset_header_within_60_second_cap(self):
        rate_limited = self._response(
            429,
            headers={
                "retry-after": "3",
                "x-ratelimit-reset-tokens": "52.35s",
            },
            payload={"error": {"message": "rate limited"}},
        )
        success = self._response(
            200,
            payload={
                "model": "synthetic-model",
                "choices": [{"message": {"content": "answer"}}],
            },
        )
        with (
            patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}),
            patch("app.model_client.load_local_env"),
            patch(
                "app.model_client.get_configured_model",
                return_value="synthetic-model",
            ),
            patch(
                "app.model_client.httpx.post",
                side_effect=[rate_limited, success],
            ) as post,
            patch("app.model_client.time.sleep") as sleep,
        ):
            answer, _ = _generate_chat_completion("system", "user")

        self.assertEqual(answer, "answer")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(52.35)

    def test_rate_limit_reset_over_60_seconds_is_not_retried(self):
        rate_limited = self._response(
            429,
            headers={
                "retry-after": "3",
                "x-ratelimit-reset-tokens": "60.01s",
            },
            payload={"error": {"message": "rate limited"}},
        )
        with (
            patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}),
            patch("app.model_client.load_local_env"),
            patch(
                "app.model_client.get_configured_model",
                return_value="synthetic-model",
            ),
            patch("app.model_client.httpx.post", return_value=rate_limited) as post,
            patch("app.model_client.time.sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
                _generate_chat_completion("system", "user")

        post.assert_called_once()
        sleep.assert_not_called()

    def test_rate_limit_retry_is_bounded_and_http_400_is_not_retried(self):
        rate_limited = self._response(
            429,
            headers={"retry-after": "0", "x-ratelimit-remaining-tokens": "0"},
            payload={"error": {"message": "rate limited"}},
        )
        bad_request = self._response(
            400,
            payload={"error": {"message": "Failed to validate JSON."}},
        )
        with (
            patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}),
            patch("app.model_client.load_local_env"),
            patch(
                "app.model_client.get_configured_model",
                return_value="synthetic-model",
            ),
            patch(
                "app.model_client.httpx.post",
                side_effect=[rate_limited, rate_limited],
            ) as post,
            patch("app.model_client.time.sleep"),
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTP 429") as raised:
                _generate_chat_completion("system", "user")

        self.assertEqual(post.call_count, 2)
        self.assertIn("x-ratelimit-remaining-tokens=0", str(raised.exception))

        with (
            patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}),
            patch("app.model_client.load_local_env"),
            patch(
                "app.model_client.get_configured_model",
                return_value="synthetic-model",
            ),
            patch(
                "app.model_client.httpx.post",
                return_value=bad_request,
            ) as post,
            patch("app.model_client.time.sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
                _generate_chat_completion("system", "user")

        post.assert_called_once()
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
