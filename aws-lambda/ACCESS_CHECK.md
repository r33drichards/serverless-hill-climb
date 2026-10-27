# Read-only access check — 2026-10-27

Credentials authenticated successfully with STS in us-east-1. Credentials are
kept outside the repository; no values or account identifiers are recorded here.

Allowed:
- Lambda ListFunctions (no functions returned in selected region)
- Lambda GetAccountSettings
- EFS DescribeFileSystems

Denied by identity-based permissions:
- freetier:GetAccountPlanState
- freetier:GetFreeTierUsage
- ecr:DescribeRepositories
- cloudformation:ValidateTemplate (both candidate templates)

Creation permissions have not been established. No AWS resources created.
Deployment is blocked on verifying the account's $0 spending boundary and obtaining
access needed for ECR + the prepared CloudFormation deployment. Lambda listing
alone is not proof of permission to create a function or pass its execution role.
See README.md for required service operations and the cleanup sequence.
