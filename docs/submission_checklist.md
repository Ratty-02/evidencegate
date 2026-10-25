# Submission checklist

Status key: DONE = finished in the repo. ENTRANT = you must do this. The full rule-by-rule
mapping is in `docs/official_rules_check.md`.

| Item | Status | Action |
|---|---|---|
| Project integrates PayPal sandbox | DONE (partial) | None. Disclosed in `docs/sandbox_limits.md`. |
| Project uses an AI model meaningfully | DONE | None. |
| Working prototype runs from the repo | DONE | Test with a fresh clone before submitting. |
| Documentation for judges | DONE | None. |
| Text description | DONE | Paste `docs/submission_text.md` into the form. |
| Tools used and how | DONE | Listed in `docs/submission_text.md`. |
| Repository URL placed in the README and form | ENTRANT | Replace `<your-username>`. |
| Repository public | ENTRANT | GitHub settings. |
| License selected in the About panel | ENTRANT | GitHub About panel. |
| Demo video under 3:00, public on YouTube | ENTRANT | Follow `docs/demo_script.md`. |
| Video free of unlicensed music and extra trademarks | ENTRANT | Review before uploading. |
| Logo rights and resemblance checked | ENTRANT | See the rules file. |
| Sponsor prize requirements read (if applicable) | ENTRANT | Not included in the rules provided. |
| Financial support declared as none | ENTRANT | On the form. |
| Final edits made before the deadline | ENTRANT | Submissions cannot be changed afterward. |

Run `python -m scripts.check_submission --tests` before you submit. It reports each automatic check and each manual item.
