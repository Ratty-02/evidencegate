"""Deterministic pre-submission checks for PayPal dispute evidence.

Verified against PayPal's Disputes API documentation:
- Evidence can be provided only while the dispute status is
  WAITING_FOR_SELLER_RESPONSE and the response includes a
  "provide-evidence" HATEOAS link.
- Accepted file types: JPG, GIF, PNG, PDF.
- Limits: 10 MB per file, 50 MB per case.

NOT yet verified: the reason-code -> required-evidence mapping.
REQUIRED_EVIDENCE is empty until it is filled from PayPal's dispute
reasons table. Do not treat an empty mapping as "no requirements".
"""
from dataclasses import dataclass, field

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".gif", ".png", ".pdf"}
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_CASE_BYTES = 50 * 1024 * 1024
ACTIONABLE_STATUS = "WAITING_FOR_SELLER_RESPONSE"
EVIDENCE_LINK_REL = "provide-evidence"

# TODO(verify): fill from PayPal dispute reasons table.
# Example shape: {"ITEM_NOT_RECEIVED": {"RECEIPT_OF_MERCHANDISE"}}
REQUIRED_EVIDENCE: dict[str, set[str]] = {}


@dataclass
class EvidenceFile:
    name: str
    size_bytes: int


@dataclass
class Issue:
    code: str
    message: str


@dataclass
class RulesResult:
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def _extension(name: str) -> str:
    dot = name.rfind(".")
    return name[dot:].lower() if dot != -1 else ""


def check_submission(
    dispute: dict,
    evidence_types: list[str],
    files: list[EvidenceFile],
) -> RulesResult:
    """Check whether a proposed evidence submission can be sent to PayPal.

    `dispute` is the dispute detail dict: needs "status", "links" (list of
    dicts with "rel"), and "reason".
    """
    result = RulesResult()

    if dispute.get("status") != ACTIONABLE_STATUS:
        result.issues.append(Issue(
            "STATUS_NOT_ACTIONABLE",
            f"dispute status is {dispute.get('status')!r}; "
            f"evidence requires {ACTIONABLE_STATUS!r}",
        ))

    rels = {link.get("rel") for link in dispute.get("links", [])}
    if EVIDENCE_LINK_REL not in rels:
        result.issues.append(Issue(
            "EVIDENCE_LINK_MISSING",
            "dispute has no provide-evidence link; PayPal will not accept evidence",
        ))

    if not evidence_types and not files:
        result.issues.append(Issue("EMPTY_SUBMISSION", "no evidence types or files provided"))

    total = 0
    for f in files:
        ext = _extension(f.name)
        if ext not in ALLOWED_EXTENSIONS:
            result.issues.append(Issue(
                "FILE_TYPE_NOT_ALLOWED",
                f"{f.name}: {ext or 'no extension'} is not JPG, GIF, PNG, or PDF",
            ))
        if f.size_bytes > MAX_FILE_BYTES:
            result.issues.append(Issue(
                "FILE_TOO_LARGE",
                f"{f.name} is {f.size_bytes} bytes; limit is {MAX_FILE_BYTES}",
            ))
        total += f.size_bytes

    if total > MAX_CASE_BYTES:
        result.issues.append(Issue(
            "CASE_TOO_LARGE",
            f"total upload is {total} bytes; case limit is {MAX_CASE_BYTES}",
        ))

    required = REQUIRED_EVIDENCE.get(dispute.get("reason", ""), set())
    missing = required - set(evidence_types)
    if missing:
        result.issues.append(Issue(
            "MISSING_EVIDENCE_TYPE",
            f"reason {dispute.get('reason')!r} requires: {sorted(missing)}",
        ))

    return result


def normalize_evidence_type(value: str) -> str:
    """Model output varies in casing and separators; PayPal names are upper snake case."""
    return value.strip().upper().replace(" ", "_").replace("-", "_")


def check_status(dispute: dict) -> RulesResult:
    """Status-only check, used for actions that do not send evidence (accept, escalate)."""
    result = RulesResult()
    if dispute.get("status") != ACTIONABLE_STATUS:
        result.issues.append(Issue(
            "STATUS_NOT_ACTIONABLE",
            f"dispute status is {dispute.get('status')!r}; "
            f"actions require {ACTIONABLE_STATUS!r}",
        ))
    return result
