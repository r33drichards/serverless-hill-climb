# Serverless Hill Climb administration

Deployment: https://serverless-hill-climb.rwendt1337.workers.dev/admin

Owner access is pinned to GitHub numeric ID `57335981`. The dedicated private
GitHub App requests `pull_requests: write` and receives `pull_request` events at
`/github/events`. Register it through **Set up with GitHub**, sign in, and choose
**Install on repositories**. Select only repositories that should receive ACKs.

App ID/client secret, private signing key, and webhook signing secret are stored
encrypted in this deployment's Durable Object. The deployment has its own
`VAULT_KEY`; it does not inherit the template's account credentials or keys.
OAuth cookies, CSRF, replay checks, and owner checks are retained from the template.
Request observability remains disabled. Never post callback URLs or keys to chat.

The admin shows the most recent job's status. `completed` means GitHub returned a
comment ID; `uncertain` means the POST outcome requires inspecting the PR before
any retry. `failed` means three bounded pre-POST attempts failed. No automatic
retry is made after a potentially successful comment POST.

This slice does not need ChatGPT sign-in or Modal execution. The template's Pi
implementation remains in source for later work, but its capability-gated generic
webhook is disabled because no WEBHOOK_KEY/BROKER_KEY is provisioned here.

Run `proofs/admin_remote.py` through the authenticated Modal SDK for tests and
bundle validation. `admin/deploy.py` runs using the existing authorized Cloudflare
CI credential route; it targets only `serverless-hill-climb` and preserves its
vault key. Production passkey-vault and durable-pi-modal are not modified.
