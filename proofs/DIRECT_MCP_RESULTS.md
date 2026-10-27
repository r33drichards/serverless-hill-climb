# Native Modal MCP transport — 2026-10-27

This is PR evidence, **not a production deployment** or a new full-model E2E claim.

## Observed

- Native pinned mcp-js image serves Streamable HTTP MCP at `/mcp` through Modal
  Sandbox Connect Tokens, without opening any raw/public unauthenticated port.
- Actual JavaScript client `admin/src/mcp.mjs` ran in a remote Node 24 sandbox.
  It initialized MCP, sent initialized notification, reused the MCP session, and
  made two real tool calls against the same live engine (`42`, then a file write/read).
- Reacquiring the same lease returned the same sandbox without renewal.
- Releasing and acquiring a new lease created a different engine; the session
  file still contained `native-http-persisted` (UTF-8 read).
- Another session's separate volume reported the file absent (`false`).
- Unauthenticated HTTP requests returned 401 for all three engine allocations.
- All three engine sandboxes and the test client terminated. Test volumes were
  deleted; a separate inventory check verified no direct-proof volumes remain.
- Image digest, sandbox IDs, observed outputs, request counts, and cleanup status
  are recorded in `direct-mcp-results.json`. No capability tokens are recorded.

## Remote regression checks

- 13 Python lifecycle/API tests passed: atomic reservation, reconnect, stale
  release, uncertain allocation, expiry, cleanup checkpoints, auth, body/field
  limits, no tool relay endpoint, and no-store capability responses.
- 33 Node tests passed: existing auth/GitHub behavior plus direct MCP JSON/SSE,
  split frames, session reuse, bounds, no retry, cleanup confirmation.
- Worker bundle and Wrangler dry-run passed.
- Final inventory: zero active sandboxes in all four proof/build apps.

## Limits

The native server describes its JS execution as stateless; process reuse is not
heap persistence. HTTP capabilities are scoped to the sandbox and its hard lifetime;
no browser token delivery or model credential transfer is introduced.

Lifecycle HTTP routing/auth tests use a fake backend, while the real-image proof
calls the same Controller/Backend via the SDK and the real JS client via HTTP.
The new lifecycle ASGI service has not been deployed publicly. No saved ChatGPT
credential, model inference, or production Cloudflare deployment was used in this
PR. A full Pi -> new controller -> native MCP integrated run remains a post-review
release gate. Hard timeout/failover under provider outage and hostile concurrent
load were not live fault-injection tested.
