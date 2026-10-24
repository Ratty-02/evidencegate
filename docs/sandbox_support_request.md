# PayPal sandbox support request

Send this to PayPal Developer Support (from developer.paypal.com) or post it in the
PayPal Developer Community. Do not include the client secret, the account
passwords, or any personal data.

---

**Subject:** Sandbox app cannot create disputes ("account not supported")

Hello,

I'm building a hackathon project (EvidenceGate) that integrates the PayPal Disputes API
in the sandbox. I can authenticate and list disputes, but I cannot create a test dispute.

- App name: EvidenceGate
- Environment: sandbox
- App Client ID: <paste from the app page; this is public>
- Sandbox business account: sb-eyhqx53091203@business.example.com
- Sandbox personal (buyer) account: sb-fzft653483210@personal.example.com

What I tried:
1. Sent a 49.00 USD payment from the personal account to the business account, choosing
   "Paying for goods or services".
2. Tried to open a dispute on that payment in the sandbox web interface. The message shown
   was: "Your account is not supported for this." (screenshot attached)
3. Confirmed that Customer disputes is enabled under Features → Add-on services.

Diagnostics from my app (attached: diagnostics.json):
- Access token: OK
- Granted OAuth scopes: <paste the granted_scopes list from diagnostics.json>
- Dispute scopes: <paste dispute_scopes, or "none">
- Dispute listing: <paste dispute_listing>

Questions:
1. Does this sandbox business account support disputes? If not, what must be enabled?
2. Please enable dispute creation (the DISPUTE_CREATE scope, if that is the required scope)
   for this sandbox app, or tell me which scope and account setting is needed.
3. If a new sandbox account pair is needed, please say so.

Thank you,
<your name>
