# Demo video script (under 3 minutes)

Record at 1080p. Narrate in plain sentences. Keep the cursor visible.

**0:00–0:20: The problem.**
"When a customer disputes a payment, the merchant has days to answer, and one wrong date can lose the case. An AI can write the answer quickly, but nothing should go out unchecked. That's the gap EvidenceGate closes. Gate the Guesswork."

**0:20–0:40: Sign-in and workspace.**
Show the sign-in page. Sign in. "Each merchant has a private workspace. Nothing one merchant does is visible to another."

**0:40–1:05: The case board.**
Show the lanes: ready, needs a human, blocked, awaiting draft, approved. Point at a blocked case. "This one is blocked by the gate. Here's why."

**1:05–1:35: One case, end to end.**
Open a case. Show the five-stage pipeline, the claims with their source records, and the uncovered-sentence warning. "Every sentence has to trace to a record. This one doesn't, so it can't go out."

**1:35–2:00: Approve a good case.**
Generate a draft on a passing case. Show the verdict. Slide to approve. Show the confirmation. "The approval is stored with a request ID. In the live version, this is the step that sends the evidence to PayPal."

**2:00–2:25: Measured, not claimed.**
Show the evaluation summary on the home page, or run `python -m evals.run_eval`. "On 29 labeled cases with injected errors, the gate caught all 21. It passed all 5 correct drafts. The paraphrase result shows where the gate is over-strict, and we report it."

**2:25–2:50: The PayPal connection, stated honestly.**
Show Settings → PayPal connection. "Authentication with PayPal's sandbox works, and disputes can be listed. Creating a test dispute is blocked by PayPal's account setup, so the write path is tested offline against PayPal's documented requests. We've sent PayPal the support request."

**2:50–3:00: Close.**
"EvidenceGate doesn't decide whether to fight. It makes sure that whatever a merchant sends is true, traceable, and approved by a person. Gate the Guesswork."
