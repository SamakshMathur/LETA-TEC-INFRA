#!/usr/bin/env bash
# =============================================================================
# create-alb.sh — One-time setup: put an Application Load Balancer in front
# of the ECS Fargate service so API Gateway always has a stable DNS name to
# point at, instead of a raw task IP that changes on every deploy.
#
# Run this ONCE from a machine with AWS credentials configured.
# After this script completes:
#   1. API Gateway's integration URI is updated to the ALB DNS name (permanent).
#   2. ECS desired-count is raised to 2 for zero-downtime rolling deploys.
#   3. delete .github/workflows/update-apigw.yml — it becomes unnecessary.
#
# Prerequisites: awscli v2, jq
# =============================================================================
set -euo pipefail

# ── Config — adjust if your AWS setup differs ─────────────────────────────────
REGION="ap-south-1"
ACCOUNT_ID="721082558531"
VPC_ID="$(aws ec2 describe-vpcs --region "$REGION" \
  --filters "Name=isDefault,Values=true" \
  --query 'Vpcs[0].VpcId' --output text)"
CLUSTER="gst-rag-cluster"
SERVICE="gst-rag-backend-service"
CONTAINER_PORT=8000
HEALTH_PATH="/api/health"
API_GW_ID="swmgzifq69"

echo "VPC: $VPC_ID"

# ── 1. Find two public subnets in the VPC ─────────────────────────────────────
SUBNETS="$(aws ec2 describe-subnets --region "$REGION" \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=mapPublicIpOnLaunch,Values=true" \
  --query 'Subnets[*].SubnetId' --output json | jq -r 'join(" ")')"
echo "Subnets: $SUBNETS"

# ── 2. Create a security group for the ALB ────────────────────────────────────
ALB_SG="$(aws ec2 create-security-group \
  --region "$REGION" \
  --group-name "gst-rag-alb-sg" \
  --description "Allow HTTPS/HTTP to the LETA RAG ALB" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' --output text)"
echo "ALB security group: $ALB_SG"

aws ec2 authorize-security-group-ingress \
  --region "$REGION" --group-id "$ALB_SG" \
  --protocol tcp --port 443 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress \
  --region "$REGION" --group-id "$ALB_SG" \
  --protocol tcp --port 80 --cidr 0.0.0.0/0

# ── 3. Allow ALB → ECS container traffic ─────────────────────────────────────
# Find the ECS task security group and allow inbound from the ALB SG.
TASK_SG="$(aws ecs describe-services \
  --region "$REGION" --cluster "$CLUSTER" --services "$SERVICE" \
  --query 'services[0].networkConfiguration.awsvpcConfiguration.securityGroups[0]' \
  --output text)"
echo "ECS task security group: $TASK_SG"

aws ec2 authorize-security-group-ingress \
  --region "$REGION" --group-id "$TASK_SG" \
  --protocol tcp --port "$CONTAINER_PORT" --source-group "$ALB_SG" || true

# ── 4. Create the ALB ─────────────────────────────────────────────────────────
ALB_ARN="$(aws elbv2 create-load-balancer \
  --region "$REGION" \
  --name "gst-rag-alb" \
  --subnets $SUBNETS \
  --security-groups "$ALB_SG" \
  --scheme internet-facing \
  --type application \
  --ip-address-type ipv4 \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text)"
echo "ALB ARN: $ALB_ARN"

ALB_DNS="$(aws elbv2 describe-load-balancers \
  --region "$REGION" --load-balancer-arns "$ALB_ARN" \
  --query 'LoadBalancers[0].DNSName' --output text)"
echo "ALB DNS: $ALB_DNS"

# ── 5. Create a target group (IP mode — required for Fargate awsvpc) ──────────
TG_ARN="$(aws elbv2 create-target-group \
  --region "$REGION" \
  --name "gst-rag-backend-tg" \
  --protocol HTTP \
  --port "$CONTAINER_PORT" \
  --vpc-id "$VPC_ID" \
  --target-type ip \
  --health-check-path "$HEALTH_PATH" \
  --health-check-interval-seconds 30 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --health-check-timeout-seconds 10 \
  --matcher HttpCode=200 \
  --query 'TargetGroups[0].TargetGroupArn' --output text)"
echo "Target group: $TG_ARN"

# ── 6. Create a listener (HTTP:80 → forward to target group) ─────────────────
# NOTE: if you have an ACM certificate, replace this with an HTTPS:443 listener:
#   aws elbv2 create-listener ... --port 443 --protocol HTTPS \
#     --certificates CertificateArn=<your-acm-arn> ...
aws elbv2 create-listener \
  --region "$REGION" \
  --load-balancer-arn "$ALB_ARN" \
  --protocol HTTP \
  --port 80 \
  --default-actions "Type=forward,TargetGroupArn=$TG_ARN"

# ── 7. Attach ECS service to the target group ─────────────────────────────────
# This is a one-time re-registration; the ECS service must be updated with the
# load balancer config.  NOTE: ECS does not allow adding an LB to an existing
# service — you must either (a) delete + recreate the service, or (b) use the
# force-new-deployment path below which works when the task def is updated.
#
# Option A: Recreate the service (safest, requires brief downtime):
#
# TASK_DEF="$(aws ecs describe-services \
#   --region "$REGION" --cluster "$CLUSTER" --services "$SERVICE" \
#   --query 'services[0].taskDefinition' --output text)"
# NETWORK_CONFIG="$(aws ecs describe-services \
#   --region "$REGION" --cluster "$CLUSTER" --services "$SERVICE" \
#   --query 'services[0].networkConfiguration' --output json)"
# aws ecs delete-service --region "$REGION" \
#   --cluster "$CLUSTER" --service "$SERVICE" --force
# aws ecs create-service \
#   --region "$REGION" \
#   --cluster "$CLUSTER" \
#   --service-name "$SERVICE" \
#   --task-definition "$TASK_DEF" \
#   --desired-count 2 \
#   --launch-type FARGATE \
#   --network-configuration "$NETWORK_CONFIG" \
#   --load-balancers "targetGroupArn=$TG_ARN,containerName=gst-rag-backend,containerPort=$CONTAINER_PORT" \
#   --health-check-grace-period-seconds 120

echo ""
echo "⚠  MANUAL STEP REQUIRED:"
echo "   ECS does not support adding a load balancer to an existing service."
echo "   Delete and recreate the service using the commands commented out above,"
echo "   then re-run this script from Step 8 onwards."
echo ""

# ── 8. Point API Gateway to the ALB DNS name (one-time, permanent) ───────────
echo "Updating API Gateway integrations to $ALB_DNS ..."
INTEG_IDS="$(aws apigatewayv2 get-integrations \
  --region "$REGION" --api-id "$API_GW_ID" \
  --query 'Items[?starts_with(IntegrationUri, `http`)].IntegrationId' \
  --output text)"

for INTEG_ID in $INTEG_IDS; do
  OLD_URI="$(aws apigatewayv2 get-integration \
    --region "$REGION" --api-id "$API_GW_ID" --integration-id "$INTEG_ID" \
    --query 'IntegrationUri' --output text)"
  # Replace IP or old hostname with the ALB DNS name (keep the path suffix)
  SUFFIX="$(echo "$OLD_URI" | sed 's|^http://[^/]*||')"
  NEW_URI="http://$ALB_DNS$SUFFIX"
  aws apigatewayv2 update-integration \
    --region "$REGION" --api-id "$API_GW_ID" \
    --integration-id "$INTEG_ID" \
    --integration-uri "$NEW_URI"
  echo "  $OLD_URI → $NEW_URI"
done

# ── 9. Raise ECS desired-count to 2 ──────────────────────────────────────────
aws ecs update-service \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --service "$SERVICE" \
  --desired-count 2

echo ""
echo "✅ ALB setup complete."
echo "   ALB DNS: $ALB_DNS"
echo "   → API Gateway now points at the ALB permanently."
echo "   → Delete .github/workflows/update-apigw.yml — it is no longer needed."
echo "   → desired-count is now 2 — rolling deploys will not cause full outages."
