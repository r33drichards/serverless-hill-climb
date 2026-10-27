# Hillclimb runtime contract

## Prompt loading and current activation gap

Load the Markdown body of `skills/hillclimb/SKILL.md` as the dedicated Hillclimb agent's system instructions; supply verified event context separately. Do not concatenate raw webhook/comment text into the system instructions. Keep the personal-agent and authentication-probe prompts separate.

This is an instruction artifact, not a live activation. The controller and Git relay are implemented on `feat/hillclimb-agent`, behind `HILLCLIMB_ENABLED`. The deployed model connection has been verified by the owner. Activation still requires verified Lambda Git/module policies, expanded installation permissions, issue-comment subscription, and a live failing-PR repair proof. The unrelated personal-agent runner remains separate. Draft code or passing unit tests are not E2E evidence.

## Git and credentials

MCP-JS's [isomorphic-git integration test](https://github.com/r33drichards/mcp-js/blob/main/tests/nixos/isomorphic-git.nix) proves a vendored ESM bundle and sandbox filesystem can init, commit and push over HTTP. It is not proof of private GitHub clone/push in this Lambda. Use a pinned, approved bundle exporting `git` and its fetch-based HTTP adapter. Enable only the required module, filesystem and network policies.

Bootstrap shape (controller-provided bindings, not a runnable deployment script):

```js
const {git, http} = await import(context.approvedGitBundleUrl);
await fs.mkdir(context.workDir, {recursive: true});
await git.clone({
  fs, http, dir: context.workDir,
  url: context.headCloneUrl,
  ref: context.headRef,
  singleBranch: true,
  depth: 1
});
const oid = await git.resolveRef({fs, dir: context.workDir, ref: 'HEAD'});
if (oid !== context.headSha) throw new Error('PR head changed; refresh before editing');
```

This is first-use only. Check for an existing checkout before cloning. Deepen history if conflict resolution requires it. Validate URLs, refs and directory identities outside the model, and bound clone size/time. See the upstream [clone API](https://isomorphic-git.org/docs/en/clone).

MCP-JS supports host/method-scoped [fetch header injection](https://github.com/r33drichards/mcp-js/blob/main/tutorials/github-api-token-injection.md) through `--fetch-header` or `--fetch-header-config`. Configure credentials outside model-visible JavaScript:

- GitHub REST: exact `api.github.com` host, `Authorization: Bearer <installation token>`.
- Git smart HTTP: exact `github.com` host, server-generated Basic authorization encoding `x-access-token:<installation token>`. Git transport auth is distinct from REST Bearer auth; see [isomorphic-git authentication](https://isomorphic-git.org/docs/en/onAuth).
- The HTTP adapter must actually use MCP-JS `fetch`, omit its own Authorization header and not expose tokens through `onAuth`. User-provided headers override injected headers.
- Do not embed credentials in clone URLs, Git config, files, prompts, stdout or comments. Avoid broad wildcard-host rules. Restrict outbound paths/methods and repository access; prevent credential-bearing redirects to unapproved destinations.
- Installation tokens expire. A trusted controller must refresh them and provide job-isolated injection, or use a vetted repository-scoped credential gateway. Do not mutate a shared Lambda's global token per concurrent job. Generic OAuth client-credentials support does not mint GitHub App installation tokens.

Request repository-scoped GitHub App permissions sufficient for `contents:write`, `pull_requests:write`, `checks:read` and `actions:read`; additional permissions only for required operations (for example Actions reruns). Existing installations may need owner acceptance of changed permissions. Workflow-file edits require the appropriate additional permission. Fail explicitly when absent.

## Durable event loop

Use a stable installation/repository/PR job key and a stable MCP session identity. Keep one writer per PR, with conditional/leased ownership. Persist head SHA, filesystem identity, phase, attempts by failure fingerprint, total iterations, pending CI/run IDs, progress-comment ID, consumed delivery/comment IDs, human guidance and side-effect intents. Store only necessary state, never tokens in prompts/checkpoints.

Verify signatures over the raw webhook body and validate installation/repository/actor scope before enqueueing. Acknowledge quickly; execute through durable jobs/alarms. Subscribe to:

- `pull_request`: `labeled` starts a job; `synchronize` refreshes its head; closing or removing the activation label stops new mutations.
- `issue_comment`: `created` on a PR handles `/hillclimb` commands from the owner or explicitly authorized maintainers. PR conversation comments use this event, not `pull_request_review_comment`. Ignore bots, self-comments, ordinary issue comments and duplicate deliveries. Verify current collaborator permission, not merely the displayed name or author association.
- CI completion events, or a bounded durable polling alarm: resume only the matching job/head. Coalesce duplicate events and do not run multiple repair loops.

GitHub documents the [webhook events and payloads](https://docs.github.com/en/webhooks/webhook-events-and-payloads#issue_comment). Comments cannot trigger this behavior until the subscription is enabled and the controller activation flag is set. The initial controller supports same-repository PRs only; fork heads explicitly block.

Lambda calls must use `wait: true`, bounded inline output and stable session recovery. Long CI waits happen outside Lambda. Runtime DynamoDB execution/console recovery must be proved on the deployed version; do not infer it from filesystem recovery or an unmerged implementation.

## Activation evidence required

Before describing the agent as live, demonstrate on an authorized test PR: label admission; private clone of its exact head; one focused fix and verified push; CI observation tied to the new SHA; a progress comment; an authorized comment reply steering the same job; rejection of unauthorized/self/duplicate events; and recovery after a fresh runtime without repeating a push/comment. Verify model inference separately from the MCP connectivity probe. Run Nix validation in GitHub Actions.
