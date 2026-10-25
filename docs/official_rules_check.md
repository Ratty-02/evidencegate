# Official rules: compliance check

This file maps each requirement in the hackathon's project and submission rules to what
this project does, and to what the entrant must still do. Items marked ENTRANT need action
before submitting.

## Project requirements

| Requirement | Status | How this project meets it |
|---|---|---|
| Integrates the PayPal developer platform (sandbox) | Met, partial | Sandbox OAuth, dispute listing, and merchant connection are verified against PayPal's sandbox. Write calls (provide-evidence, accept-claim) and webhook verification are implemented and tested offline. The sandbox cannot yet create a dispute (see `docs/sandbox_limits.md`). |
| AI tool, model, or platform | Met | Groq-hosted `openai/gpt-oss-120b` drafts structured claims. A deterministic gate checks every output. |
| PayPal integration is central, not decorative | Met | Disputes, evidence rules, and submission are built around PayPal's dispute data and endpoints. |
| Built or significantly updated in the submission period | Met | Created during the hackathon. Not a pre-existing project. |
| Works on the platform it's intended for | Met | Desktop web application (Python 3.11+, any modern browser). Tests run offline. |
| Third-party SDKs, APIs, and data used with authorization | Met | See "Third-party services and licenses" below. |

## Submission requirements

| Requirement | Status | How this project meets it |
|---|---|---|
| Text description of features and functionality | Met | `docs/submission_text.md` |
| Functional demo judges can run | Met | README "For judges" runs in mock mode with no PayPal credentials. |
| Public code repository with setup instructions | ENTRANT | Repository is ready. Make it public and replace `<your-username>` in the README with your real URL. |
| Open-source license visible in the About section | ENTRANT | `LICENSE` (MIT) is in the root. Select it under the repository's About panel. |
| Demo video under three minutes | ENTRANT | Follow `docs/demo_script.md`. Record on the desktop browser the app is built for. |
| Video shows the project functioning on its intended device | ENTRANT | Screen recording of the desktop browser counts. |
| Video is public on YouTube, linked on the form | ENTRANT | Upload as public. |
| No unlicensed music or third-party trademarks in the video | ENTRANT | No music. PayPal sandbox screens appear for the integration. Keep them brief, and don't show other brands. |
| Testing access for judges | Met | Mock mode needs no credentials. Judges sign up with any email (dev mode shows the verification link). |
| English materials | Met | All materials are in English. |
| Single entrant (no team representative needed) | Met | Solo entry. |

## Intellectual property and eligibility

| Requirement | Status | Notes |
|---|---|---|
| Original work, solely owned by the entrant | ENTRANT | Confirm the logo's image generator terms allow commercial use, and check for resemblance to existing marks. Dependencies are listed below. |
| No violation of third-party IP | ENTRANT | Review the logo and video as noted above. |
| No financial or preferential support from the Sponsor or Administrator | Met | None received. Declare this on the form. |
| Submission frozen after the submission period | ENTRANT | Finish all edits before the deadline. After submitting, changes are not allowed. |
| Sponsor prize requirements (section 8) | ENTRANT | Not included in the rules provided. Read them before entering for a sponsor prize. |

## Third-party services and licenses

| Component | Use | License or terms to confirm |
|---|---|---|
| PayPal REST APIs (sandbox) | Authentication, disputes, webhook verification | PayPal Developer Terms. Use of the sandbox only; no live funds. |
| Groq API | Model inference | Groq API terms. Free tier for development and evaluation. |
| FastAPI, Starlette, Pydantic, Uvicorn | Web framework and server | MIT, BSD, and similar permissive licenses |
| Jinja2, httpx, python-dotenv, python-multipart | Templates, HTTP client, configuration, uploads | BSD and MIT |
| cryptography | Encrypts stored PayPal credentials | Apache 2.0 or BSD |
| pytest | Tests | MIT |
| Inter, Manrope (Google Fonts) | Typography | SIL Open Font License |
| Postman | Collection of PayPal requests | Used only to produce the JSON collection |
| Render | Hosting, if the demo is deployed | Render terms |

## Items for the entrant to confirm before submitting

1. The logo's generator terms allow commercial use, and no close resemblance to an existing mark.
2. The repository URL in the README is replaced, and the repository is public with the MIT license shown.
3. The video is under three minutes, uses no music, and shows the desktop application.
4. Sponsor prize requirements, if you enter for one.
5. Financial support declaration on the form: none received.
