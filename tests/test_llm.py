import json

import httpx
import pytest

from app.ai.llm import GroqClient, LLMOutputError, parse_draft

VALID = {
    "evidence_types": ["RECEIPT_OF_MERCHANDISE"],
    "response_text": "The item was delivered on 2026-10-06.",
    "claims": [
        {"statement": "Delivered on 2026-10-06", "record_id": "TRK-1001",
         "field": "delivered_on", "value": "2026-10-06"}
    ],
    "recommendation": "FIGHT",
    "reason": "Tracking shows delivery before the dispute date.",
}


def test_valid_json_parses_to_draft():
    draft = parse_draft(json.dumps(VALID))
    assert draft.recommendation == "FIGHT"
    assert draft.claims[0].record_id == "TRK-1001"


def test_markdown_fences_are_stripped():
    raw = "```json\n" + json.dumps(VALID) + "\n```"
    assert parse_draft(raw).recommendation == "FIGHT"


def test_non_json_is_rejected():
    with pytest.raises(LLMOutputError, match="valid JSON"):
        parse_draft("Sure! Here is your draft: ...")


def test_missing_field_is_rejected():
    bad = {k: v for k, v in VALID.items() if k != "claims"}
    with pytest.raises(LLMOutputError, match="schema"):
        parse_draft(json.dumps(bad))


def test_unknown_recommendation_is_rejected():
    bad = {**VALID, "recommendation": "MAYBE"}
    with pytest.raises(LLMOutputError, match="schema"):
        parse_draft(json.dumps(bad))


def test_client_sends_request_and_parses_reply():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        content = json.dumps(VALID)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = GroqClient(api_key="test-key", base_url="https://example.test/v1",
                        model="test-model", transport=httpx.MockTransport(handler))
    draft = client.draft("system prompt", "user prompt")

    assert draft.recommendation == "FIGHT"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["model"] == "test-model"
    assert seen["body"]["temperature"] == 0


def test_client_without_key_refuses_to_call():
    client = GroqClient(api_key="", base_url="https://example.test/v1",
                        transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        client.complete("s", "u")
