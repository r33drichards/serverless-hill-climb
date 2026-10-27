# Serverless Hill Climb

Private, template-derived Cloudflare deployment. This first slice receives GitHub
`pull_request` / `labeled` webhooks and posts a fixed acknowledgement when the exact
label is **hill climb** or **hillclimb**. No code changes, merges, model calls, or Modal allocations
occur at runtime. The Pi/Modal implementation from the template is retained for
future slices; its credentials and live deployment are not copied.

## Setup

Admin: https://serverless-hill-climb.rwendt1337.workers.dev/admin

1. Choose **Set up with GitHub**, creating the dedicated private GitHub App.
2. Sign in as `r33drichards` (numeric owner ID `57335981`).
3. Select **Install on repositories**, then select the repositories to watch.
4. Apply the exact `hill climb` or `hillclimb` label to an open PR in an installed repository
   owned by that account.

GitHub configures the signed webhook at `/github/events` from the app manifest.
The app asks for pull-request read/write permission, not repository content write.
Its private key and webhook secret are encrypted using the deployment's own
`VAULT_KEY`. GitHub consent/installation is a browser step; deployments alone do
not grant repository access. No ChatGPT sign-in is required for this fixed ACK.

## Behavior and limits

- GitHub HMAC-SHA256 validated before parsing/acceptance; payload limit 1 MiB.
- Installation and repository numeric owner IDs checked. Tokens are short-lived
  and scoped to the single target repository with pull-request write permission.
- An encrypted Durable Object queue accepts at most 50 pending jobs. One fixed
  comment per repository ID/PR number, even after removing/reapplying the label.
- Rechecks PR state and label before commenting. Ignores other events and labels.
- Persists POST intent before the side effect. Uncertain POST outcomes never
  auto-retry; the owner must inspect the PR. Pre-POST failures retry at most three
  times. Admin shows the most recent job status.
- Retains up to 5,000 PR receipts, then rejects further admission until a future
  explicit retention/migration operation. No silent dedupe expiry.
- Do not enable request logging: OAuth callback URLs contain temporary codes.

## Development and deployment

`proofs/admin_remote.py` runs the tests, bundle, and Wrangler validation on a
bounded Modal sandbox, retrieves artifacts and verifies termination. No npm work
runs on the Gateway. `admin/deploy.py` uses the existing authorized Cloudflare CI
route and targets only `serverless-hill-climb`, preserving its encryption key.
It does not modify `durable-pi-modal` or the production passkey-vault Worker.

Template documentation under `admin/`, `broker/`, and historical `proofs/`
describes the original deployment. It is not evidence that this derivative has
completed an actual GitHub installation or real webhook/comment test.

## Proposed direct Modal MCP transport

This branch replaces the tool-relaying broker with a small acquire/release
controller. Pi talks directly to the pinned native mcp-js HTTP server through
Modal Connect authentication, reusing one bounded sandbox per run. See
[the transport design and rollout](broker/README.md) and
[PR verification evidence](proofs/DIRECT_MCP_RESULTS.md).
The live ACK-only deployment has not been changed by this work.
