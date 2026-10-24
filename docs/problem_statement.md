# Problem statement

**Project:** EvidenceGate, a gate that stops unsupported payment dispute responses before they reach PayPal.

**Who is affected.** Merchants who receive PayPal disputes and respond through PayPal's Disputes API, usually with a small team or no dedicated dispute staff.

**The problem.** A dispute response has to satisfy two things. It must meet PayPal's rules: the dispute must still be open, the evidence link must exist, and files must be an allowed type and size. And every factual statement in the response must be backed by a record the merchant actually holds. Writing a response quickly, especially under a deadline, is where mistakes happen: a delivery date is stated wrongly, or a sentence claims something no record supports. Those mistakes can get a response rejected or weaken the case.

**What EvidenceGate does.** An AI model drafts the response, and each sentence is tied to a claim with a source record. The gate then checks rules, grounding, and sentence coverage. Anything that fails blocks approval. The merchant approves every submission, and the approval is stored with a request ID.

**What it does not do.** It does not judge whether fighting is the right choice. It warns when cited records suggest the fight may be weak, and it never decides for the merchant.

**Honest scope.** PayPal provides dispute and transaction data, but not tracking or delivery records. Merchants supply those as CSV. In this prototype, PayPal's sandbox currently has no disputes, so the case board shows mock disputes, and the real PayPal read path is verified only up to listing.
