# Resolve the adapter tag to an immutable digest before the test image build.
ARG ADAPTER_IMAGE=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0
FROM ${ADAPTER_IMAGE} AS adapter
FROM docker.io/wholelottahoopla/mcp-js@sha256:2f2752f606a5ded1a2044aa6ddc3691a7833fe4ea9517351c806d6136b606083
COPY --from=adapter /lambda-adapter /opt/extensions/lambda-adapter
COPY fs.rego /opt/lambda-test/fs.rego
ENV PORT=8080 AWS_LWA_PORT=8080 \
    AWS_LWA_READINESS_CHECK_PATH=/api/version \
    AWS_LWA_READINESS_CHECK_HEALTHY_STATUS=200 \
    AWS_LWA_READINESS_CHECK_TIMEOUT_SECONDS=8 \
    AWS_LWA_INVOKE_MODE=buffered \
    HOME=/tmp
WORKDIR /tmp
# Keep the native mcp-v8 ENTRYPOINT. No Python/FastAPI relay.
CMD ["--session-id","lambda-test","--policies-json","{\"filesystem\":{\"policies\":[{\"url\":\"file:///opt/lambda-test/fs.rego\"}]}}"]
