#!/usr/bin/env bash
# infra/provision-staging.sh
# ─────────────────────────────────────────────────────────────────────────────
# One-time script to create the LETA staging ECS service.
# Run this once — after that, deploy-staging.yml maintains it.
#
# Prerequisites:
#   aws CLI configured, ECS cluster already exists, ECR repo already exists.
#   The staging image must exist: push one with `workflow_dispatch` on deploy-staging.yml
#   first, OR push a :staging-latest tag manually from your local machine.
#
# Usage:
#   bash infra/provision-staging.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REGION="ap-south-1"
CLUSTER="gst-rag-cluster"
STAGING_SERVICE="gst-rag-backend-staging-service"
STAGING_FAMILY="gst-rag-backend-staging"
ACCOUNT="446550122628"

# ── These must already exist in your AWS account ──────────────────────────────
# Subnets and security group — reuse the same ones as production (or create new)
SUBNETS="${SUBNETS:-}"            # comma-separated subnet IDs, e.g. subnet-abc,subnet-def
SECURITY_GROUPS="${SECURITY_GROUPS:-}"   # sg-xxxxxxxx

if [[ -z "$SUBNETS" || -z "$SECURITY_GROUPS" ]]; then
  echo "Set SUBNETS and SECURITY_GROUPS before running."
  echo "  export SUBNETS=subnet-abc123,subnet-def456"
  echo "  export SECURITY_GROUPS=sg-0abc123def456"
  exit 1
fi

# ── 1. Create CloudWatch log group for staging ────────────────────────────────
echo "→ Creating log group /ecs/gst-rag-backend-staging"
aws logs create-log-group \
  --log-group-name /ecs/gst-rag-backend-staging \
  --region "$REGION" 2>/dev/null || echo "  (already exists)"

# ── 2. Register staging task definition ──────────────────────────────────────
echo "→ Registering task definition: $STAGING_FAMILY"
aws ecs register-task-definition \
  --region "$REGION" \
  --cli-input-json file://rag-backend/.aws/task-definition-staging.json

# ── 3. Create ECS service (1 task — staging doesn't need HA) ─────────────────
echo "→ Creating ECS service: $STAGING_SERVICE"
SUBNET_LIST=$(echo "$SUBNETS" | tr ',' ' ')
aws ecs create-service \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --service-name "$STAGING_SERVICE" \
  --task-definition "$STAGING_FAMILY" \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SECURITY_GROUPS],assignPublicIp=ENABLED}" \
  --scheduling-strategy REPLICA \
  || echo "  Service already exists — use 'aws ecs update-service' to modify."

echo ""
echo "✓ Staging service provisioned."
echo "  Service ARN: arn:aws:ecs:$REGION:$ACCOUNT:service/$CLUSTER/$STAGING_SERVICE"
echo ""
echo "Next steps:"
echo "  1. Push the staging image (trigger deploy-staging.yml via workflow_dispatch)"
echo "  2. Point staging.letatec.com DNS at this service's public IP (or add an ALB)"
echo "  3. Set the real secret values via AWS Secrets Manager or ECS secrets"
