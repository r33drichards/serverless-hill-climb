# Modal direct fallback proof — 2026-10-27

Actual Docker image: `docker.io/wholelottahoopla/mcp-js@sha256:2f2752f606a5ded1a2044aa6ddc3691a7833fe4ea9517351c806d6136b606083` (Docker Hub amd64 manifest for `0.23.0-rc.1`).

Direct Modal SDK allocation succeeded. The image retains its Docker ENTRYPOINT; pass only engine arguments to Sandbox.create, not the executable again.

`proofs/modal_probe.py` initialized MCP over private sandbox stdio and called the real `run_js` tool with `console.log(6 * 7)`. Observed tool result: `{"output":"42"}`, `isError:false`.

Bounds: 0.25 CPU, 512 MiB, 60-second hard timeout. No exposed HTTP port. Sandbox explicitly terminated after the result. No Cloudflare deployment or Pi loop yet. Persistent volumes and session isolation still require verification.

## Volume proof — 2026-10-27

`volume_probe.py` ran remotely against the same pinned engine image. Session A wrote
`/data/owner`, terminated, and read `session-a` after sandbox recreation. Session B
mounted a different Volume, could not see A's file, and wrote its own value. A's
value remained unchanged on a subsequent recreation. All four sandboxes terminated;
SDK active inventory for `durable-pi-modal-volume-proof` returned `[]`.

Exact observations: `volume-results.json`. Test Volumes were ephemeral resources
held across sandbox recreations, then released after the test. This establishes
Volume persistence across sandbox lifetimes, not long-term named-volume retention.
File I/O in this proof used sandbox exec, not the engine's policy-gated fs API.
Cross-session broker authentication remains untested. The initial probe attempt
stopped because explicit termination raises SandboxTerminatedError by default;
using wait(raise_on_termination=False) fixed the harness, not the service.

## Next implementation handoff

- No application is deployed yet. Do not call the storage proof an E2E Pi proof.
- Add a narrow engine filesystem policy for `/data/workspace`, and prove actual
  run_js writes/reads through it. Use named session Volumes in the application.
- Implement authenticated broker with private sandbox stdio, fenced single-writer
  leases, bounded execution, and explicit termination. No public engine tunnel.
- Upstream Pi repo now resolves to `earendil-works/pi`; inspected agent package is
  `@earendil-works/pi-agent-core` version `1.4.0`, depending on matching `pi-ai`.
  Verify npm availability and Workers bundling remotely before selecting it.
  Its real Agent requires a model + streamFn; do not replace these with a scripted
  result or assume the gateway's model credentials may be copied to deployments.
- Inspect available deployment secret *names* and authorized model-provider route,
  without exposing values. If no zero-cost authorized model route exists, report
  that precise blocker rather than pretending an agent ran.
- Then durable webhook admission/checkpointing, duplicate handling, two-session
  auth rejection, full real-model/tool E2E test, and cleanup evidence.
- GCP leftover inventory has not been verified by this continuation.

## Deployment prerequisite check — 2026-10-27 continuation

Read-only credential inventory completed without retrieving secret values or
allocating compute:

- GitHub Actions secrets for `durable-pi-modal`: none.
- Existing `passkey-vault` CI: `CLOUDFLARE_API_TOKEN` is present; production unchanged.
- OpenClaw protected secret store: empty.
- Modal selected default environment: metadata keys `GH_TOKEN`, `LAYA_OTLP_TOKEN`,
  and `HF_TOKEN`. No configured Pi inference endpoint/model or demonstrated
  zero-cost inference entitlement was found in this deployment's configuration.
  Presence of an HF token does not establish inference access or free quota.

The live real-Pi acceptance test is blocked on selecting and configuring an
application-authorized model endpoint/model with included quota and no overages.
Gateway model authentication has not been exported to the application. Do not
substitute a deterministic streamFn or mock model and call it a real agent proof.
User action: designate the model-provider route and provision its application
credential privately (or designate an already-authorized credential). Modal compute
spending controls are accepted and do not need reconfirmation.

No broker or webhook was deployed by this continuation. Existing engine/storage
proofs remain valid within their stated scope; full E2E remains unfinished. No
new compute resources were allocated. GCP inventory remains unverified.

## Provider decision — 2026-10-27

User selected Sign in with ChatGPT for Pi, superseding the request to choose an
API-key provider. Use Pi's upstream ChatGPT OAuth integration; do not silently
fall back to paid API billing or export gateway credentials. Upstream currently
contains `packages/ai/src/auth/oauth/openai-chatgpt.ts` and `openai-codex.ts`.
Pin and verify the selected Pi version before implementation. Complete an
application-specific private login and verify a real inference request; provider
selection alone is not completed authentication. Keep refresh credentials outside
the mcp-js session filesystem and logs. Deployment remains unfinished.

Official integration reference:
https://developers.openai.com/siwc/token-sharing-open-source
Distinguish the user's personal self-hosted agent from offering a remotely hosted
multi-user service; the latter has separate integration eligibility requirements.

## Admin deployment — 2026-10-27

Live owner setup: https://durable-pi-modal.rwendt1337.workers.dev/admin

- Source implementation commit: `986a098` (subsequent smoke-client correction
  changes only deployment verification, not the Worker bundle).
- GitHub owner numeric ID verified through GitHub API: `57335981`.
- 15/15 auth/security tests passed on a bounded direct Modal Node sandbox.
  Includes wrong-account rejection, state/cookie/CSRF protections, callback replay,
  actual signed JWT verification, encrypted persistence, serialized refresh,
  uncertain-exchange rejection, and logout/disconnect behavior. Provider exchanges
  in these tests are synthetic, not live account consent or inference.
- esbuild bundle and Wrangler 4.153.0 dry-run passed remotely. Every build sandbox
  was terminated; final application sandbox inventory was empty.
- Isolated Worker and SQLite OwnerAuthority deployed. New encryption key was
  generated only in CI and installed as a Worker secret. A subsequent deployment
  used `keep_bindings` to retain secret bindings. No production vault changes.
- Successful deployment/check run:
  https://github.com/r33drichards/passkey-vault/actions/runs/40432160226
- Live HTTP observations: `/health` 200, `/admin` 200 with GitHub setup form,
  unauthenticated `/admin/chatgpt` and POST `/admin/chatgpt/start` 401,
  `/internal/credential` and `/webhook` 404, invalid setup callback 400.
- Initial CI deployment succeeded but its smoke client received Cloudflare 1010
  with Python's default user agent. A descriptive application User-Agent corrected
  the check; no Cloudflare security controls were disabled.
- Modal SDK filesystem API here is `sandbox.filesystem.write_text(data,path)`
  and `read_text(path)`, not `sandbox.open`. The build harness was corrected.

Owner action: open `/admin`, register the private no-repository-permission GitHub
App, sign in with GitHub, then connect ChatGPT using the private callback form.
Live browser OAuth consent and inference remain unverified until the owner does
this. Credentials will be encrypted for later webhook integration; webhook/Pi/
broker execution is still disabled and is not claimed complete.

## GitHub setup callback repair — 2026-10-27

- Reproduced the reported generic HTTP 500 on the live setup callback using an
  independent fresh state/cookie and an intentionally invalid, non-secret code.
- Root cause: `redirect: 'error'` is unsupported by Cloudflare Workers and throws
  before dispatch. Changed provider fetches to `manual`; non-2xx responses still
  fail closed, including every redirect. No credential forwarding is introduced.
- Source fix: `a1a187d`. All 16 remote security tests, bundle and Wrangler dry-run
  passed. Modal build sandbox terminated; application active inventory `[]`.
- Deployment succeeded: https://github.com/r33drichards/passkey-vault/actions/runs/40432747858
  Existing encryption key and Durable Object data preserved.
- After deployment, the same synthetic live callback now yields the expected
  handled provider rejection (502), not the previous runtime exception (500).
  Reproducer: `proofs/github_callback_probe.py`. No owner code or token was used.
- Real owner browser consent still needs a fresh setup attempt from `/admin`;
  the previous callback's state was reserved and must not be replayed. If GitHub
  says the app name is taken by the failed registration, choose a unique name.

## Live integrated acceptance — 2026-10-27 01:41 UTC

**This section supersedes earlier unfinished/blocker statuses.** User completed
private ChatGPT consent. Server-side credential decryption succeeded. Real
`@earendil-works/pi-agent-core` and `pi-ai` 1.4.0 bundled for Workers with
`nodejs_compat`; 19 remote security/checkpoint tests and Wrangler dry-run passed.

- Standalone real Pi inference: `gpt-6.1-sol`, HTTP 200, `response.completed`,
  exact output `PI_AUTH_OK`. Saved OAuth only; no API-key fallback. A first catalog
  processing attempt failed; increasing the 512 KiB bound to 4 MiB allowed discovery.
- Inference evidence CI: https://github.com/r33drichards/passkey-vault/actions/runs/40433518140
- Integrated deployment CI: https://github.com/r33drichards/passkey-vault/actions/runs/40433984469
- Temporary verification capability removed by CI after use. No provider tokens,
  callback codes, or provider response bodies were logged or exported.
- Broker deployed with private per-sandbox stdio. A first image-resolution attempt
  failed before allocation; the reserved lease blocked premature retry. Explicit
  remote image build/resolution corrected it; no unsafe lease bypass was used.
- Upstream image digest unchanged:
  `docker.io/wholelottahoopla/mcp-js@sha256:2f2752f606a5ded1a2044aa6ddc3691a7833fe4ea9517351c806d6136b606083`.
  Derived policy-only Modal image: `im-wpacPP0MhtAXUsZExQRJrQ`.
- `write-ae1ca22b14`: authenticated durable webhook → real Pi → broker → real
  mcp-js wrote and read `pi-file-ae1ca22b14`. Engine result `isError:false`.
- `read-ae1ca22b14`: a different sandbox on the same named session Volume read
  that exact marker. This is actual engine filesystem I/O, not sandbox shell I/O.
- `isolation-ae1ca22b14`: a distinct session Volume returned `ISOLATED=true`.
- All three runs completed with two real model responses and one tool each.
  Duplicate deliveries returned the same tool ledger and finished timestamp;
  no additional engine execution. Unauthorized webhook/status/broker requests 401.
- All three integrated engine sandboxes explicitly terminated. Active engine
  inventory `[]`; test Volumes for both sessions and the preliminary `proof-a`
  probe deleted and confirmed absent. Modal app inventory showed broker tasks `0`.
  Deployed service retained at zero warm containers. Build sandboxes also absent.

Exact sanitized events/sandbox IDs/results/cleanup: `e2e-results.json`.
Reproducer: `e2e_smoke.py`; operating bounds and limitations: `../broker/README.md`.
No assertion of automatic arbitrary crash recovery or live heap restoration:
uncertain in-flight side effects stop for reconciliation rather than replay.
