# Direct native MCP on Modal (PR implementation; not deployed)

```
Cloudflare Pi ── acquire/release ──> authenticated lifecycle controller
       └──── MCP HTTP + Connect Token ──> native mcp-js sandbox
```

`app.py` no longer relays tool requests through `/tool`. It only allocates and
releases one bounded engine per run. Pi initializes native MCP at `/mcp` and sends
all tool calls directly to that sandbox, through Modal's authenticated Connect
proxy. No FastAPI proxy, HTTP sidecar, or JavaScript wrapper is added to the engine.

The historical `durable-pi-modal-broker` deployment is **not changed** by this PR.
The new app/ledger/secret names are isolated under `serverless-hill-climb-lifecycle`.
The GitHub ACK-only slice does not allocate engines and is unaffected.

## Lifecycle API

Both endpoints require `Authorization: Bearer <BROKER_KEY>`, independently of
ChatGPT credentials. JSON fields are allowlisted and bodies capped at 1 KiB.

- `POST /leases/acquire`: `{"session":"my-session","lease":"64-lowercase-hex"}`.
  Returns `lease`, `sandbox`, `url`, `token`, `until`, `image`. Treat the response as
  a secret: it has `Cache-Control: no-store`. Never print it or use query tokens.
- `POST /leases/release`: `{"lease":"64-lowercase-hex"}`. Returns
  `{"lease":"...","terminated":true}` only after verified termination or
  conservative expiry of an unresolved allocation. Release is idempotent.
- `/tool` is gone. Acquiring an active lease reconnects to the same sandbox;
  acquiring a released/uncertain lease never silently allocates a replacement.

One active writer is supported globally. An atomic Modal Dict slot reserves before
allocation, and a fixed live sandbox name adds a provider-side overlap guard. The
HTTP service serializes operations and scales to zero with max one container.
Never run independent controllers against the same ledger. Avoid overlapping
controller deployments: drain/release the active lease before changing versions.

Sandbox hard lifetime: **240 seconds**, 0.25 CPU, 512 MiB; zero warm engines.
The **300-second** reservation includes allocation uncertainty and is not a token
renewal or promise that the sandbox lives that long. Reconnect never extends it.
The controller is 0.25 CPU/256 MiB, max one instance, 90-second request ceiling.
There is no idle renewal, background task, or paid fallback.

## Authentication and persistence

No raw ports (`encrypted_ports`, `h2_ports`, `unencrypted_ports`) are opened.
`create_connect_token(port=8080)` authenticates requests at Modal's proxy before
native mcp-js sees them. Pi sends the capability only in an Authorization header,
never follows redirects, and does not store it in the transcript/lease ledger.
Stopping the sandbox removes the reachable engine; hard timeout bounds exposure
if cleanup cannot run. The engine receives no model or controller credentials.

Pinned image:
`docker.io/wholelottahoopla/mcp-js@sha256:2f2752f606a5ded1a2044aa6ddc3691a7833fe4ea9517351c806d6136b606083`.
The existing derived image `im-wpacPP0MhtAXUsZExQRJrQ` adds only `fs.rego`.
It retains its ENTRYPOINT and runs with `PORT=8080`.

Each session gets a separate `hill-climb-session-<owner/session hash>` Volume.
Only `/data/workspace` file operations permitted by `fs.rego` are available.
The current pinned server advertises **stateless JS execution**. Reusing its
process and MCP session does not promise that JS globals survive tool calls.
Files are durable across sandbox recreation; JavaScript heap state is not.

## Checkpoints and failure handling

Cloudflare records each tool intent before its direct HTTP request and the result
afterward. MCP request IDs are correlation IDs, **not** idempotency keys. A lost
response may mean a side effect occurred; neither client nor controller replays
it. The webhook's existing durable admission record suppresses duplicate runs.
Pi performs initialize + initialized notification once, reuses Mcp-Session-Id,
handles bounded JSON/SSE responses, and releases the engine on success/failure.
An interrupted-run alarm attempts release without replaying tool/model calls.

After an uncertain acquire, release the same lease ID. The controller reconciles
by stored sandbox ID or its fixed live name. If no sandbox can be found before the
reservation expires, it stays blocked instead of assuming the create failed.
If the caller crashes, the hard sandbox lifetime stops compute; the reservation
remains fail-closed until an authenticated operator repeats release. Cleanup
failure is recorded as `cleanup-unverified`, not reported as successful execution.

Modal Dict entries are not a permanent application ledger; Cloudflare run records
remain authoritative. This is a single-owner prototype, not distributed CAS-based
multi-controller leasing or transparent process/heap recovery.

## Validation

Using the authenticated Modal SDK interpreter (no heavy local work):

```
python proofs/lifecycle_tests_remote.py
python proofs/admin_remote.py
python proofs/direct_mcp.py
```

The first two run tests/builds remotely. The third runs this PR's actual JavaScript
MCP client in a credential-free Node sandbox (apart from temporary test-only
Connect capabilities) against the pinned native engine, with an ephemeral lease
ledger and unique disposable volumes. It proves unauthorized rejection, two calls
on one engine, reconnect reuse, recreation persistence, session isolation, and
cleanup. It never uses ChatGPT authorization or deploys a public controller.
Read `proofs/direct-mcp-results.json` and `proofs/DIRECT_MCP_RESULTS.md` for observed
results and limits. Tests require existing free quota/blocking spending controls.

## Deployment after review (not performed by this PR)

1. Provision a new Modal Secret `serverless-hill-climb-lifecycle-auth` containing
   a fresh `BROKER_KEY`. Keep the existing broker's key/deployment untouched.
2. From repository root deploy `modal deploy broker/app.py`. The image ID is
   workspace-specific; for another workspace build the same pinned registry
   image with `fs.rego` and record its resolved image ID.
3. Provision the same key as a Worker secret and set `BROKER_URL` to the new
   lifecycle service origin. Deploy the Worker bundle from this same commit.
   The ACK-only deployment script intentionally does not provision these values.
4. Enable the generic Pi webhook only with its separate `WEBHOOK_KEY` and an
   independently authorized ChatGPT connection. Run one bounded integrated Pi
   smoke before claiming full-model E2E success for this transport.
5. Drain active leases before upgrading. Rollback needs the matching previous
   Worker + old `/tool` broker; mixing old/new protocols will fail closed.
