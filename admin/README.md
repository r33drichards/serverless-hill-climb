# Owner-only admin

Personal deployment for GitHub account ID `57335981` (`r33drichards`). This does
not expose a multi-user hosted model service. `/webhook` is now enabled with a
separate owner capability; `/runs?id=...` returns encrypted-at-rest run records
only to that capability. See `../broker/README.md` for bounded runtime behavior.

## First login

1. Visit `/admin` and choose **Set up with GitHub**. Confirm creation of a private
   GitHub App under your personal account. No repository permissions are requested.
2. The app manifest callback checks GitHub's returned numeric owner ID before
   storing the app's OAuth configuration. Other accounts cannot claim setup.
3. Complete **Continue with GitHub**. The server exchanges the code, fetches
   GitHub `/user`, and matches the same fixed numeric ID. The GitHub token is not
   persisted. A secure eight-hour owner session is issued.
4. Select **Connect ChatGPT**, then **Continue with ChatGPT**. Approve the agent
   in the new tab. If the localhost callback cannot load, paste its entire URL
   into the private admin form. Never paste it into chat.
5. The server verifies state, PKCE grant, signed ID-token issuer/audience/expiry/
   nonce/subject, and ChatGPT plan scope before storing the credential encrypted.

The one-time GitHub App registration requires the owner in their browser; there
is no preexisting app credential for this new project. No API keys are requested.

## Security and operations

- One SQLite Durable Object owns the configuration and credential authority.
- AES-256-GCM with purpose-bound authenticated data encrypts app secrets, OAuth
  pending state, model credentials, and signed-in browser cookie contents.
  `VAULT_KEY` is a Worker secret generated in CI, never an artifact or git file.
  Subsequent deployments preserve it; key rotation requires explicit migration.
- Cookies are `__Host-`, Secure, HttpOnly, SameSite=Lax. Forms check exact Origin
  and session CSRF tokens. Responses are non-cacheable and unframeable.
- OAuth exchanges reserve their one-use state before dispatch. Uncertain token
  exchange/refresh is not blindly retried. Single-object serialization protects
  rotating refresh tokens. Logout invalidates all admin sessions.
- Reconnection retains the prior identity/client registration. To switch ChatGPT
  accounts, explicitly disconnect first. Local disconnect is not provider-side
  revocation; remove the app in ChatGPT settings to revoke it there too.
- No token-export endpoint, public model proxy, login cron, or sandbox credential
  mount. The credential is read internally by the real Pi runtime; neither it nor
  refresh credentials are returned to the webhook caller or Modal broker.
- Worker request observability is disabled so callback URLs are not collected
  by application request logs. Never enable unsanitized request tracing.
- Browser sign-in and real inference require owner consent and must be reported
  separately from synthetic protocol tests and deployment HTTP checks.

## Verification and deployment

Run `proofs/admin_remote.py` with the authenticated Modal SDK. It transfers only
source files to a bounded credential-free Node sandbox, installs pinned packages,
runs security tests, bundles, and performs a Wrangler dry-run; then retrieves the
bundle/lockfile and terminates the sandbox. No npm work runs on the Gateway.

`deploy.py` runs in the existing authorized GitHub CI credential route. It targets
only the new `durable-pi-modal` Worker, creates the SQLite migration on first
deployment, preserves its encryption secret on subsequent deploys, and verifies
public access-control responses. It never changes the production vault Worker.

## References

- [GitHub App manifest flow](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest)
- [OpenAI registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [OpenAI ID-token validation](https://developers.openai.com/siwc/website)
- Cuse design reference: commit `921659abbdccae4a20b903276a87fefdb106a2f5`,
  `cloudflare/src/chatgpt-login.ts`. This implementation replaces IRC confirmation
  with the authenticated admin session and adds signed ID-token verification.

### Callback transport regression

Cloudflare Workers does not implement Fetch's `redirect: 'error'`. Use `manual`
and reject non-2xx responses so OAuth secrets are never forwarded to redirect
locations. Node-only mocked fetch tests do not exercise this runtime difference.

While initial setup is pending, `python3 proofs/github_callback_probe.py` checks
the live callback with its own fresh cookie/state and a deliberately invalid
(non-secret) code. Expect a handled provider rejection (502), not an unhandled
runtime failure (500). It never uses the owner's callback or installs an app.
Once setup is complete the probe exits without submitting a request to GitHub.

## Live verification

Pi agent-core and pi-ai are pinned to 1.4.0. Inference uses only the saved OAuth
access token at `https://api.openai.com/v1/responses`, `store:false`, `stream:true`,
no automatic retries and no API-key fallback. A bounded model-catalog fetch
selects an available account model; this deployment verified `gpt-6.1-sol`.
The diagnostic `/ops/verify` requires a temporary CI-only capability, which CI
deletes after verification. Its encrypted one-shot result contains no credentials.
Catalog processing succeeded after raising the initial 512 KiB bound to 4 MiB.

Deployment now additionally needs CI secrets `DURABLE_PI_BROKER_KEY` and
`DURABLE_PI_WEBHOOK_KEY`, passed as `BROKER_KEY` and `WEBHOOK_KEY`. Both were
provisioned privately; the broker key is separate from the webhook capability.
