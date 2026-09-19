"""Tests for the assistant service, driven through its public methods by a scripted model."""
import json
from typing import Any, Dict

from app.services.assistant_service import ANSWER_ERROR_TEXT, AssistantService
from tests.fakes import ScriptedChatModel

METADATA = {
    "title": "Water bill March 2024",
    "correspondent": "City Water",
    "document_date": "2024-03-01",
    "document_type": "invoice",
    "summary": "Monthly water bill.",
    "suggested_tags": ["water bill", "utilities"],
}

UNKNOWN_METADATA: Dict[str, Any] = {
    "title": "Unknown",
    "correspondent": "Unknown",
    "document_date": None,
    "document_type": "Unknown",
    "summary": "",
    "suggested_tags": [],
}

HISTORY = [
    {"role": "user", "content": "Do I have any vet bills?"},
    {"role": "assistant", "content": "Yes, two from Oak Street Vet."},
]


class TestExtractMetadata:
    def test_parses_plain_json_reply(self):
        model = ScriptedChatModel(json.dumps(METADATA))

        metadata = AssistantService(model).extract_metadata("Some bill text", "bill.pdf")

        assert metadata == METADATA

    def test_parses_json_wrapped_in_code_fences(self):
        model = ScriptedChatModel(f"```json\n{json.dumps(METADATA)}\n```")

        metadata = AssistantService(model).extract_metadata("Some bill text")

        assert metadata == METADATA

    def test_unparseable_reply_falls_back_to_unknown(self):
        model = ScriptedChatModel("Sure! This document looks like a water bill.")

        metadata = AssistantService(model).extract_metadata("Some bill text")

        assert metadata == UNKNOWN_METADATA

    def test_json_that_is_not_an_object_falls_back_to_unknown(self):
        model = ScriptedChatModel('["water bill"]')

        metadata = AssistantService(model).extract_metadata("Some bill text")

        assert metadata == UNKNOWN_METADATA

    def test_model_error_falls_back_to_unknown(self):
        model = ScriptedChatModel(TimeoutError("no reply"))

        metadata = AssistantService(model).extract_metadata("Some bill text")

        assert metadata == UNKNOWN_METADATA

    def test_sends_document_text_and_filename_deterministically(self):
        model = ScriptedChatModel(json.dumps(METADATA))

        AssistantService(model).extract_metadata("Amount due: $42.17", "bill.pdf")

        [messages] = model.calls
        assert [message.role for message in messages] == ["system", "user"]
        assert "Amount due: $42.17" in messages[1].content
        assert "bill.pdf" in messages[1].content
        assert model.options == [{"temperature": 0.0, "max_tokens": 500}]

    def test_skips_reconciliation_without_existing_tags(self):
        model = ScriptedChatModel(json.dumps(METADATA))

        metadata = AssistantService(model).extract_metadata("Some bill text", existing_tags=[])

        assert metadata["suggested_tags"] == ["water bill", "utilities"]
        assert len(model.calls) == 1


class TestTagReconciliation:
    def test_maps_generated_tags_to_existing_tags(self):
        model = ScriptedChatModel(json.dumps(METADATA), '```json\n["water bill", "utility"]\n```')

        metadata = AssistantService(model).extract_metadata(
            "Some bill text", existing_tags=["utility", "tax return"]
        )

        assert metadata["suggested_tags"] == ["water bill", "utility"]
        reconcile_prompt = model.calls[1][-1].content
        assert '["water bill", "utilities"]' in reconcile_prompt
        assert '["utility", "tax return"]' in reconcile_prompt
        assert model.options[1] == {"temperature": 0.0, "max_tokens": 500}

    def test_model_error_keeps_generated_tags(self):
        model = ScriptedChatModel(json.dumps(METADATA), ConnectionError("host down"))

        metadata = AssistantService(model).extract_metadata(
            "Some bill text", existing_tags=["utility"]
        )

        assert metadata["suggested_tags"] == ["water bill", "utilities"]
        assert metadata["title"] == "Water bill March 2024"

    def test_unparseable_reply_keeps_generated_tags(self):
        model = ScriptedChatModel(json.dumps(METADATA), "I would map utilities to utility.")

        metadata = AssistantService(model).extract_metadata(
            "Some bill text", existing_tags=["utility"]
        )

        assert metadata["suggested_tags"] == ["water bill", "utilities"]


class TestRewriteQuery:
    def test_skipped_without_history(self):
        model = ScriptedChatModel()

        query = AssistantService(model).rewrite_query("Where is my passport?", [])

        assert query == "Where is my passport?"
        assert model.calls == []

    def test_rewrites_follow_up_using_history(self):
        model = ScriptedChatModel('"Oak Street Vet bills"\n')

        query = AssistantService(model).rewrite_query("How much were they?", HISTORY)

        assert query == "Oak Street Vet bills"
        prompt = model.calls[0][-1].content
        assert "ASSISTANT: Yes, two from Oak Street Vet." in prompt
        assert "How much were they?" in prompt

    def test_model_error_falls_back_to_original_question(self):
        model = ScriptedChatModel(TimeoutError("no reply"))

        query = AssistantService(model).rewrite_query("How much were they?", HISTORY)

        assert query == "How much were they?"

    def test_empty_reply_falls_back_to_original_question(self):
        model = ScriptedChatModel("  ")

        query = AssistantService(model).rewrite_query("How much were they?", HISTORY)

        assert query == "How much were they?"


class TestGenerateAnswer:
    def test_returns_reply_with_context_and_history(self):
        model = ScriptedChatModel("The vet bills total $180.")

        answer = AssistantService(model).generate_answer(
            "How much were they?", ["Invoice: $80", "Invoice: $100"], HISTORY
        )

        assert answer == "The vet bills total $180."
        [messages] = model.calls
        assert [message.role for message in messages] == ["system", "user", "assistant", "user"]
        assert messages[1].content == "Do I have any vet bills?"
        assert messages[2].content == "Yes, two from Oak Street Vet."
        assert "Document excerpt 2:\nInvoice: $100" in messages[3].content
        assert "How much were they?" in messages[3].content
        assert model.options == [{"temperature": 0.3, "max_tokens": 1000}]

    def test_keeps_only_last_ten_history_messages(self):
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i}"}
            for i in range(12)
        ]
        model = ScriptedChatModel("Answer.")

        AssistantService(model).generate_answer("Question?", ["chunk"], history)

        history_sent = [message.content for message in model.calls[0][1:-1]]
        assert history_sent == [f"message {i}" for i in range(2, 12)]

    def test_model_error_returns_apology(self):
        model = ScriptedChatModel(ConnectionError("host down"))

        answer = AssistantService(model).generate_answer("Question?", ["chunk"])

        assert answer == ANSWER_ERROR_TEXT
