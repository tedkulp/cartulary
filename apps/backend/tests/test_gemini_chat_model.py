"""Tests for the Gemini chat model adapter.

The offline tests use a local Gemini-compatible REST endpoint and real sockets. The
contract tests talk to Gemini and only run with `pytest --live`.
"""
import pytest

from app.config import settings
from app.providers import Message, ModelConfigurationError, ModelError
from app.providers.gemini import GeminiChatModel
from tests.fakes import FakeJsonEndpoint


def generated(text):
    return {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}
        ]
    }


class TestGeminiChatModel:
    def test_sends_system_messages_as_system_instruction(self):
        with FakeJsonEndpoint(generated("Hello back.")) as endpoint:
            model = GeminiChatModel(
                api_key="gemini-key", model="gemini-test", timeout=5, base_url=endpoint.base_url
            )

            reply = model.chat(
                [
                    Message(role="system", content="Be brief."),
                    Message(role="user", content="Hello."),
                    Message(role="assistant", content="Hi."),
                    Message(role="user", content="Again."),
                ],
                temperature=0.3,
                max_tokens=1000,
            )

        assert reply == "Hello back."
        [request] = endpoint.requests
        assert request.path.startswith("/v1beta/models/gemini-test:generateContent")
        assert request.headers["x-goog-api-key"] == "gemini-key"
        assert request.body["systemInstruction"] == {"parts": [{"text": "Be brief."}]}
        assert request.body["contents"] == [
            {"role": "user", "parts": [{"text": "Hello."}]},
            {"role": "model", "parts": [{"text": "Hi."}]},
            {"role": "user", "parts": [{"text": "Again."}]},
        ]
        assert request.body["generationConfig"] == {"temperature": 0.3, "maxOutputTokens": 1000}

    def test_joins_several_system_messages(self):
        with FakeJsonEndpoint(generated("ok")) as endpoint:
            model = GeminiChatModel(
                api_key="k", model="gemini-test", timeout=5, base_url=endpoint.base_url
            )

            model.chat(
                [
                    Message(role="system", content="Be brief."),
                    Message(role="system", content="Be kind."),
                    Message(role="user", content="Hello."),
                ]
            )

        assert endpoint.requests[0].body["systemInstruction"] == {
            "parts": [{"text": "Be brief.\n\nBe kind."}]
        }

    def test_without_system_messages_or_options_sends_neither(self):
        with FakeJsonEndpoint(generated("ok")) as endpoint:
            model = GeminiChatModel(
                api_key="k", model="gemini-test", timeout=5, base_url=endpoint.base_url
            )

            model.chat([Message(role="user", content="Hello.")])

        body = endpoint.requests[0].body
        assert "systemInstruction" not in body
        assert body.get("generationConfig", {}) == {}


class TestGeminiChatModelFailures:
    """Every provider failure surfaces as ModelError."""

    def test_missing_api_key_raises_a_configuration_error(self):
        model = GeminiChatModel(api_key=None, model="gemini-test", timeout=5)

        with pytest.raises(ModelConfigurationError, match="GEMINI_API_KEY"):
            model.chat([Message(role="user", content="hello")])

    def test_blocked_reply_raises_model_error(self):
        blocked = {"promptFeedback": {"blockReason": "SAFETY"}}
        with FakeJsonEndpoint(blocked) as endpoint:
            model = GeminiChatModel(
                api_key="k", model="gemini-test", timeout=5, base_url=endpoint.base_url
            )

            with pytest.raises(ModelError):
                model.chat([Message(role="user", content="hello")])

    def test_error_response_raises_model_error(self):
        error = {
            "error": {"code": 400, "message": "API key not valid", "status": "INVALID_ARGUMENT"}
        }
        with FakeJsonEndpoint(error, status=400) as endpoint:
            model = GeminiChatModel(
                api_key="bad", model="gemini-test", timeout=5, base_url=endpoint.base_url
            )

            with pytest.raises(ModelError):
                model.chat([Message(role="user", content="hello")])

    def test_unreachable_host_raises_model_error(self, unused_port):
        model = GeminiChatModel(
            api_key="k", model="gemini-test", timeout=5, base_url=f"http://127.0.0.1:{unused_port}"
        )

        with pytest.raises(ModelError):
            model.chat([Message(role="user", content="hello")])

    def test_timeout_raises_model_error(self, silent_server):
        model = GeminiChatModel(
            api_key="k", model="gemini-test", timeout=0.2, base_url=silent_server
        )

        with pytest.raises(ModelError):
            model.chat([Message(role="user", content="hello")])

    def test_images_raise_a_configuration_error(self):
        model = GeminiChatModel(api_key="k", model="gemini-test", timeout=5)

        with pytest.raises(ModelConfigurationError, match="images"):
            model.chat([Message(role="user", content="Read this.", images=[b"\x89PNG"])])


@pytest.mark.live
class TestGeminiChatModelContract:
    """Contract tests against Gemini, using GEMINI_API_KEY and LLM_MODEL."""

    def test_chat_follows_system_instruction(self):
        model = GeminiChatModel(
            api_key=settings.GEMINI_API_KEY, model=settings.LLM_MODEL, timeout=60
        )

        reply = model.chat(
            [
                Message(role="system", content="Always reply with only the word CARTULARY."),
                Message(role="user", content="Say hello."),
            ],
            temperature=0.0,
        )

        assert "cartulary" in reply.lower()

    def test_missing_model_raises_model_error(self):
        model = GeminiChatModel(
            api_key=settings.GEMINI_API_KEY, model="cartulary-no-such-model", timeout=60
        )

        with pytest.raises(ModelError):
            model.chat([Message(role="user", content="hello")])
