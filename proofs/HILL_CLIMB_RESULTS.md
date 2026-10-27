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
