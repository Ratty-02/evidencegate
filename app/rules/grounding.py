"""Check that every factual claim in a draft maps to a real source record.

A claim is SUPPORTED when the cited record exists, has the cited field,
and the value matches after normalizing case and whitespace.
A claim is UNSUPPORTED when it cites no record, an unknown record, or an
unknown field. A claim is CONTRADICTED when the record disagrees.

uncovered_sentences() finds sentences in the response that no claim
accounts for. A sentence is covered when some claim's words all appear in
it. Limitation: this is word-based, so a paraphrase that changes a key
word (e.g. "delivery" vs "delivered") is flagged for review rather than
passed silently.
"""
import re
from dataclasses import dataclass

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_TOKEN = re.compile(r"[a-z0-9]+")


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


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


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


def uncovered_sentences(response_text: str, claims: list[Claim]) -> list[str]:
    """Return response sentences that no claim accounts for."""
    claim_sets = [_tokens(c.statement) for c in claims if _tokens(c.statement)]
    uncovered = []
    for sentence in _SENTENCE_SPLIT.split(response_text.strip()):
        words = _tokens(sentence)
        if not words:
            continue
        if not any(claim_words <= words for claim_words in claim_sets):
            uncovered.append(sentence.strip())
    return uncovered
