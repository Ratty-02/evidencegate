"""Check that every factual claim in a draft maps to a real source record.

A claim is SUPPORTED when the cited record exists, has the cited field,
and the value matches after normalizing case and whitespace.
A claim is UNSUPPORTED when it cites no record, an unknown record, or an
unknown field. A claim is CONTRADICTED when the record disagrees.

Limitation: matching is exact after normalization. Dates and amounts must
be written in the same format as the record. Fuzzy or semantic matching
is out of scope for this module.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Claim:
    statement: str
    record_id: str | None
    field: str | None
    value: str | None


@dataclass(frozen=True)
class ClaimResult:
    claim: Claim
    status: str  # "SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED"
    reason: str


def _norm(value) -> str:
    return " ".join(str(value).strip().lower().split())


def check_claims(claims: list[Claim], records: dict[str, dict]) -> list[ClaimResult]:
    results = []
    for claim in claims:
        if not claim.record_id or claim.record_id not in records:
            results.append(ClaimResult(claim, "UNSUPPORTED", "no known source record cited"))
            continue
        record = records[claim.record_id]
        if claim.field not in record:
            results.append(ClaimResult(
                claim, "UNSUPPORTED",
                f"field {claim.field!r} not found in record {claim.record_id!r}",
            ))
            continue
        actual = record[claim.field]
        if _norm(actual) == _norm(claim.value):
            results.append(ClaimResult(claim, "SUPPORTED", "matches source record"))
        else:
            results.append(ClaimResult(
                claim, "CONTRADICTED",
                f"record says {actual!r}, draft says {claim.value!r}",
            ))
    return results


def submission_blocked(results: list[ClaimResult]) -> bool:
    """Block submission if any claim is not fully supported."""
    return any(r.status != "SUPPORTED" for r in results)
