# Problem statement

**EvidenceGate: stop unsupported payment dispute responses before they go out.**

**Who is affected.** Merchants who sell online and receive PayPal payment disputes. Most have no dispute team. A response is drafted under a deadline by one person, often by copying facts from several tools.

**The problem.** A dispute response has to meet two standards. PayPal's rules require the dispute to still be open, the evidence link to exist, and files to be an allowed type and size. The facts in the response must also be true and traceable. A wrong delivery date, or a sentence that claims something no record shows, can get the response rejected or weaken the case. Nothing in a typical workflow checks the facts before submission.

**What EvidenceGate does.** An AI model drafts the response, and each sentence is tied to a claim with a source record. A deterministic gate then checks PayPal's rules, claim-to-record grounding, and whether every sentence is backed by a claim. Any failure blocks approval. The merchant approves every submission, and each approval is stored with a request ID.

**What makes it different.** Most dispute tools automate drafting and submission. EvidenceGate's central feature is the refusal to send what it cannot trace. The model is treated as untrusted; the checks are ordinary code that can be tested.

**Evidence that it works.** On 29 labeled cases with errors injected by the author, the gate caught all 21 injected errors and passed all 5 clean drafts. Sentence-coverage false blocks on accurate paraphrases are measured separately (`evals/results/paraphrase.json`).

**Honest scope.**
- PayPal does not provide tracking or delivery proof. Merchants supply records as CSV.
- The gate checks facts and PayPal's rules. It does not judge whether fighting is the right decision; it issues advisory warnings instead.
- PayPal sandbox dispute creation is blocked by PayPal's account configuration. The read path works against the sandbox; the write path is tested offline against PayPal's documented request shapes.
