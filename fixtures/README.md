# Fixtures

These files are ASSUMED shapes, written to match the PayPal dispute fields
the code reads (id, status, reason, links, amount). They are synthetic.

Before relying on them for the demo, create a real sandbox dispute, save the
show-details response, and update these files to match. Record any
differences in docs/sandbox_limits.md.

- disputes.json: dispute summaries with the record IDs each one cites
- records.json: transaction and tracking records the drafts must match
