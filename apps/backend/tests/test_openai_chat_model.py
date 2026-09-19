"""Tests for the OpenAI chat model adapter.

The offline tests use a local OpenAI-compatible endpoint and real sockets. The contract
tests talk to OpenAI and only run with `pytest --live`.
"""
import pytest

from app.config import settings
from app.providers import Message, ModelError
from app.providers.openai import OpenAIChatModel
from tests.fakes import FakeJsonEndpoint


def completion(content):
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-test",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }


class TestOpenAIChatModel:
    def test_sends_messages_and_options_and_returns_reply(self):
        with FakeJsonEndpoint(completion("Hello back.")) as endpoint:
            model = OpenAIChatModel(
                api_key="openai-key",
                model="gpt-test",
                timeout=5,
                base_url=f"{endpoint.base_url}/v1",
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
        assert request.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer openai-key"
        assert request.body["model"] == "gpt-test"
        assert request.body["messages"] == [
            {"role": "system", "content": "Be brief."},
            {"role": "user", "content": "Hello."},
            {"role": "assistant", "content": "Hi."},
            {"role": "user", "content": "Again."},
        ]
        assert request.body["temperature"] == 0.3
        assert request.body["max_tokens"] == 1000

    def test_leaves_unset_options_to_the_provider(self):
        with FakeJsonEndpoint(completion("ok")) as endpoint:
            model = OpenAIChatModel(
                api_key="k", model="gpt-test", timeout=5, base_url=f"{endpoint.base_url}/v1"
            )

            model.chat([Message(role="user", content="Hello.")])

        assert "temperature" not in endpoint.requests[0].body
        assert "max_tokens" not in endpoint.requests[0].body

    def test_empty_reply_is_empty_text(self):
        with FakeJsonEndpoint(completion(None)) as endpoint:
            model = OpenAIChatModel(
                api_key="k", model="gpt-test", timeout=5, base_url=f"{endpoint.base_url}/v1"
            )

            assert model.chat([Message(role="user", content="Hello.")]) == ""


class TestOpenAIChatModelFailures:
    """Every provider failure surfaces as ModelError."""

    def test_missing_api_key_raises_model_error(self):
        model = OpenAIChatModel(api_key=None, model="gpt-test", timeout=5)

        with pytest.raises(ModelError, match="OPENAI_API_KEY"):
            model.chat([Message(role="user", content="hello")])

    def test_error_response_raises_model_error(self):
        error = {"error": {"message": "Incorrect API key", "type": "invalid_request_error"}}
        with FakeJsonEndpoint(error, status=401) as endpoint:
            model = OpenAIChatModel(
                api_key="bad", model="gpt-test", timeout=5, base_url=f"{endpoint.base_url}/v1"
            )

            with pytest.raises(ModelError):
                model.chat([Message(role="user", content="hello")])

    def test_unreachable_host_raises_model_error(self, unused_port):
        model = OpenAIChatModel(
            api_key="k", model="gpt-test", timeout=5, base_url=f"http://127.0.0.1:{unused_port}/v1"
        )

        with pytest.raises(ModelError):
            model.chat([Message(role="user", content="hello")])

    def test_timeout_raises_model_error(self, silent_server):
        model = OpenAIChatModel(
            api_key="k", model="gpt-test", timeout=0.2, base_url=f"{silent_server}/v1"
        )

        with pytest.raises(ModelError):
            model.chat([Message(role="user", content="hello")])

    def test_images_raise_model_error(self):
        model = OpenAIChatModel(api_key="k", model="gpt-test", timeout=5)

        with pytest.raises(ModelError, match="images"):
            model.chat([Message(role="user", content="Read this.", images=[b"\x89PNG"])])


@pytest.mark.live
class TestOpenAIChatModelContract:
    """Contract tests against OpenAI, using OPENAI_API_KEY and LLM_MODEL."""

    def test_chat_returns_text(self):
        model = OpenAIChatModel(
            api_key=settings.OPENAI_API_KEY, model=settings.LLM_MODEL, timeout=60
        )

        reply = model.chat(
            [
                Message(role="system", content="Reply with exactly one word."),
                Message(role="user", content="Say hello."),
            ],
            temperature=0.0,
            max_tokens=10,
        )

        assert isinstance(reply, str)
        assert reply.strip()

    def test_missing_model_raises_model_error(self):
        model = OpenAIChatModel(
            api_key=settings.OPENAI_API_KEY, model="cartulary-no-such-model", timeout=60
        )

        with pytest.raises(ModelError):
            model.chat([Message(role="user", content="hello")])
