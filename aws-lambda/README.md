# Current scope: Lambda only

User narrowed the test on 2026-10-27: no EFS, no VPC, temporary files only.
Use direct AWS APIs, not CloudFormation. The native image plus AWS Lambda Web
Adapter remains the intended packaging. `fs.rego` now permits only `/tmp/` file
operations. `function.yaml` is a reference definition only, with no EFS/VPC fields.
Do not deploy `infra.yaml`: it belongs to the superseded EFS proposal below.

Attempt to create the dedicated ECR repository was denied with
`ecr:CreateRepository` for IAM user `sincere-ape`. No AWS resources were created.
The new ECR permissions are not effective for this operation yet. Resume with
repository creation, remote image build/push, a minimal Lambda execution role,
and a bounded IAM-only invocation test when that access is fixed.

## Superseded EFS proposal — reference only

# Disposable native mcp-js AWS Lambda test — preparation only

Status: not built, validated in AWS, or deployed. Waiting for private AWS access
and verification of account eligibility/spending limits. Default proposed region:
us-east-1. Keep all resources isolated from existing deployments.

Use the maintained AWS Lambda Web Adapter with the existing pinned native image:
https://github.com/aws/aws-lambda-web-adapter

No custom broker/handler is introduced. The native HTTP server remains the
ENTRYPOINT; the adapter supplies the Lambda invocation interface. Resolve and
record the adapter image digest before building; deploy the ECR output by digest.
The local Dockerfile is a candidate, not a verified compatible Lambda artifact.

## Proposed test scope

- IAM-authenticated synchronous Lambda Invoke with HTTP API v2 events; no Function
  URL, API Gateway, or public endpoint. No asynchronous invocation/retry.
- 512 MiB RAM, 30-second invocation limit, reserved concurrency one, no provisioned
  concurrency. Small fixed test code only; no model credentials.
- Encrypted Regional EFS with Bursting throughput, automatic backups disabled,
  one access point /mnt/workspace. One mount target/AZ for this disposable test.
- Dedicated VPC/subnet/security groups, no NAT/IGW/paid endpoints/public IPv4.
  Container has no external network egress. No CloudWatch log-write permission;
  consume sanitized synchronous responses and retain only nonsecret evidence.
- ECR is private and charged separately. All allowance is account-wide; the Lambda
  free allowance does not establish that EFS/ECR are free for this account.

## Credential and cost gate

Use private operator credential provisioning or a supported authenticated AWS
profile. Do not paste access keys/session tokens into IRC or commit them. Prefer
short-lived AWS credentials. Verify STS identity, region, session expiry, actual
Free Tier/credit eligibility and a blocking $0 spending boundary before allocation.
A budget alert or reserved concurrency alone is not a hard spending cap. If the
account cannot meet that boundary, stop before create operations.

Needed operations are limited to the two test stacks: CloudFormation, private ECR
image push, IAM execution-role creation/PassRole, Lambda configuration/Invoke,
VPC subnet/security-group/ENI management, and EFS filesystem/access-point/mount
management. Temporary build credentials should permit only the test ECR repository.
Never forward general account credentials into the engine image or test events.

## Deploy/prove/cleanup sequence once access is available

1. Check existing resources and account constraints, validate both CloudFormation
   templates, and review the change sets. Do not alter existing stacks/roles.
2. Create `infra.yaml` with a unique test stack name. Wait for its mount target to
   be ready. Record its outputs privately; do not record credentials.
3. Build linux/amd64 on a verified remote worker (not the Gateway), push to the
   new ECR repository, and record immutable source/adapter/output digests.
4. Create `function.yaml` using the infrastructure outputs and image digest.
5. Invoke native health and actual JS execution; write a tiny file under
   /mnt/workspace. Use synchronous MCP operations only; async jobs can be frozen
   when an invocation returns. Explicitly test transport behavior across cold
   starts: legacy MCP session IDs are process-local and are NOT durable via EFS.
6. Force a new execution environment and demonstrate the file survives. Do not
   infer persistence from two warm invocations. Record failures as failures.
7. Delete the function stack, wait for Lambda network interfaces to detach, empty
   only the test ECR repository, then delete the infrastructure stack. This removes
   the disposable EFS test data. Verify no test functions, images/repositories,
   EFS resources, ENIs or stacks remain.

This does not migrate the application or replace production Modal services.
