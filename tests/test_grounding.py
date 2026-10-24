from app.rules.grounding import Claim, check_claims, submission_blocked

RECORDS = {
    "trk_1": {"delivered_on": "2026-03-05", "status": "DELIVERED", "signed_by": "R. Shah"},
}


def test_supported_claim():
    c = Claim("Delivered on 2026-03-05", "trk_1", "delivered_on", "2026-03-05")
    [r] = check_claims([c], RECORDS)
    assert r.status == "SUPPORTED"
    assert not submission_blocked([r])


def test_value_comparison_ignores_case_and_spacing():
    c = Claim("Status delivered", "trk_1", "status", "  delivered ")
    [r] = check_claims([c], RECORDS)
    assert r.status == "SUPPORTED"


def test_contradicted_claim_blocks_submission():
    c = Claim("Delivered on 2026-03-03", "trk_1", "delivered_on", "2026-03-03")
    [r] = check_claims([c], RECORDS)
    assert r.status == "CONTRADICTED"
    assert "2026-03-05" in r.reason
    assert submission_blocked([r])


def test_claim_without_record_is_unsupported():
    c = Claim("Customer confirmed receipt", None, None, None)
    [r] = check_claims([c], RECORDS)
    assert r.status == "UNSUPPORTED"
    assert submission_blocked([r])


def test_claim_citing_unknown_record_is_unsupported():
    c = Claim("Shipped via FedEx", "trk_999", "carrier", "FedEx")
    [r] = check_claims([c], RECORDS)
    assert r.status == "UNSUPPORTED"


def test_claim_citing_unknown_field_is_unsupported():
    c = Claim("Signed by R. Shah", "trk_1", "recipient", "R. Shah")
    [r] = check_claims([c], RECORDS)
    assert r.status == "UNSUPPORTED"
    assert "recipient" in r.reason


def test_all_supported_does_not_block():
    claims = [
        Claim("Delivered on 2026-03-05", "trk_1", "delivered_on", "2026-03-05"),
        Claim("Signed by R. Shah", "trk_1", "signed_by", "R. Shah"),
    ]
    assert not submission_blocked(check_claims(claims, RECORDS))
