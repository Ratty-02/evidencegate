from app.rules.grounding import Claim, uncovered_sentences


def test_fully_covered_response_has_no_uncovered_sentences():
    claims = [Claim("The item was delivered on 2026-10-06.", "TRK-1001", "delivered_on", "2026-10-06")]
    assert uncovered_sentences("The item was delivered on 2026-10-06.", claims) == []


def test_extra_sentence_without_claim_is_flagged():
    claims = [Claim("The item was delivered on 2026-10-06.", "TRK-1001", "delivered_on", "2026-10-06")]
    text = "The item was delivered on 2026-10-06. The buyer requested a refund on 2026-10-05."
    assert uncovered_sentences(text, claims) == ["The buyer requested a refund on 2026-10-05."]


def test_no_claims_means_every_sentence_is_uncovered():
    assert len(uncovered_sentences("First fact. Second fact.", [])) == 2
