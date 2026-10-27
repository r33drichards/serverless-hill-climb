# Hill Climb slice evidence

Repository generated from `r33drichards/durable-pi-modal` on 2026-10-27.
Dedicated deployment: `serverless-hill-climb`; no inherited credentials.

Verification in progress. Real GitHub App installation and signed webhook ->
comment verification require the owner's browser consent on the deployed admin.
Synthetic tests are not a substitute for that live test.

## Remote validation

- 27 tests passed on Node 24 in bounded Modal sandbox
  `sb-01M5XJAPGZHQ8KXHHN04H5P3H7`.
- Includes GitHub signature rejection, exact-label matching, owner restriction,
  PKCS#1 signing-key conversion and JWT verification, repository-scoped token
  request, successful ACK, duplicate suppression, closed PR skip, bounded retry,
  and no comment replay after ambiguous POST or interrupted checkpoint.
- Bundle and Wrangler dry-run passed. Sandbox terminated; active inventory `[]`.
- Dedicated CI route commit: `r33drichards/passkey-vault@2f93a2a`.
- Run: https://github.com/r33drichards/passkey-vault/actions/runs/40437676103

These mocked GitHub tests prove code behavior, not a real installed GitHub App.

## Deployed checks

CI run `40437676103` completed successfully. Independent live checks confirmed:

- `/health` returns 200 with service `serverless-hill-climb`.
- `/admin` returns 200 and its manifest requests only `pull_requests: write`,
  subscribes to `pull_request`, and sets the active hook to this Worker's
  `/github/events` endpoint.
- Unconfigured `/github/events` returns 503 (not accepting events before setup).
- Unauthenticated `/admin/chatgpt` and generic `/webhook` return 401.
- `/internal/credential` returns 404.
- `hill climb` label created on the new repository.

**Pending owner action:** create/install the dedicated GitHub App in the admin
browser flow. No real GitHub webhook or posted ACK is claimed yet. After installation,
open a test PR, add `hill climb`, verify one app-authored ACK, then remove/reapply
label and redeliver the event to confirm no additional comment.
