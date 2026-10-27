# Minimal deployed runtime

- Admin: https://durable-pi-modal.rwendt1337.workers.dev/admin
- Webhook: `POST https://durable-pi-modal.rwendt1337.workers.dev/webhook`
- Status: `GET https://durable-pi-modal.rwendt1337.workers.dev/runs?id=EVENT_ID`
- Broker: `POST https://r33drichards--durable-pi-modal-broker-service.us-east.modal.run/tool`

Webhook/status require `Authorization: Bearer <WEBHOOK_KEY>`; the broker requires
its **different** `BROKER_KEY`. Neither is a ChatGPT token. Keep these operator
capabilities private. The Cloudflare CI route holds them as GitHub Actions secrets;
ChatGPT access/refresh credentials remain encrypted inside OwnerAuthority only.

Webhook JSON: `{"id":"unique-event","session":"my-session","prompt":"...","timestamp":MILLISECONDS_SINCE_EPOCH}`.
Timestamp must be within five minutes, event ID 1–80 alphanumeric/underscore/hyphen,
session 1–64 lowercase alphanumeric/hyphen, prompt at most 4,000 characters.
Admission returns 202; duplicate event+session+prompt returns the existing status,
while a conflicting payload returns 409. Ownership always derives from the fixed
owner capability, not a supplied tenant. The owner may address their own sessions.

## Bounds and recovery

One active owner run; four model turns and four tools; 240-second run deadline;
45-second model-request limit; 120-second hard engine lifetime; 0.25 CPU/512 MiB
engine; 0.25 CPU/256 MiB broker; zero warm containers and max one broker container.
The broker's persistent global allocation lease prevents overlapping writers,
including uncertain creates; its TTL exceeds sandbox lifetime. Each tool has an
idempotency digest and a reserve-before-dispatch ledger. Unknown side effects are
not replayed. An alarm encountering an in-progress run marks it interrupted rather
than silently reissuing model/tool requests. This is fail-closed checkpointing,
not transparent automatic recovery of arbitrary side effects.

Run records and tool results are encrypted in the Durable Object. At most 100
accepted run records are admitted before explicit operator retention maintenance.
The broker ledger contains only engine requests' digests/results/lease metadata,
never model credentials. Do not treat its cache as the permanent webhook ledger;
Cloudflare's retained run records govern webhook deduplication.

Each session gets a distinct named Volume, mounted only at `/data`. File access is
limited by `fs.rego` to read/write/exists/stat beneath `/data/workspace/`, without
`..` or destination operations. No filesystem symlink creation, network, subprocess,
or import policy is granted to mcp-js. Files survive sandbox recreation; heap state
does not. Production session volumes are retained until explicit deletion. Test
volumes were deleted after proof; this intentionally removes their file contents.

## Reproduction

Use the authenticated Modal SDK interpreter for `modal deploy broker/app.py`.
The pinned upstream digest is in `app.py`. The derived Modal image in
`engine-image.txt` adds only `/etc/durablepi/fs.rego` to that pinned image. To rebuild
it for another Modal workspace, use the SDK's
`modal.Image.from_registry(IMAGE).add_local_file('broker/fs.rego', '/etc/durablepi/fs.rego', copy=True).build(app)`
and replace the image ID in `app.py` with the returned ID before deploying.
All image work runs remotely.

Run the reproducible HTTP smoke orchestration (no installs/builds locally):

```sh
WEBHOOK_KEY_FILE=/private/webhook-key \
BROKER_KEY_FILE=/private/broker-key \
python3 proofs/e2e_smoke.py
```

Provide capability files through protected operator/CI provisioning, not chat.
The script makes three real Pi/model runs and writes `proofs/e2e-results.json`.
It verifies unauthorized rejection, duplicate no-reexecution, actual engine output,
different sandbox IDs for persistence, and a second session's missing file.
Afterward, verify `modal.Sandbox.list(app_id=...)` is empty and delete only the two
reported test volumes. Their names are `durable-pi-session-` plus the first 24 hex
characters of SHA-256 of `57335981:SESSION`. Verify deletion by failed hydration.
Keep the deployed scale-to-zero broker; do not stop the live service as cleanup.

19 remote security/checkpoint tests and a Wrangler dry run passed. Live integrated
proof is separate from those synthetic tests. Abrupt provider failure, distributed
outage recovery, and hostile concurrent load are not claimed live-tested.
