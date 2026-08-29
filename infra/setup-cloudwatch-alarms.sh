#!/usr/bin/env bash
# infra/setup-cloudwatch-alarms.sh
# ─────────────────────────────────────────────────────────────────────────────
# One-time script to create CloudWatch alarms for the LETA production backend.
# Idempotent — re-running updates existing alarms to these exact thresholds.
#
# Prerequisites:
#   aws CLI configured with a role that can write CloudWatch alarms
#   An SNS topic for notifications (set SNS_ALERT_ARN below)
#
# Usage:
#   SNS_ALERT_ARN=arn:aws:sns:ap-south-1:446550122628:leta-alerts bash infra/setup-cloudwatch-alarms.sh
#
# Find your ALB name:
#   aws elbv2 describe-load-balancers --query 'LoadBalancers[*].LoadBalancerArn'
# Then extract the suffix after app/ for the ALB metric dimension.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REGION="ap-south-1"
CLUSTER="gst-rag-cluster"
SERVICE="gst-rag-backend-service"

# ── Set these for your environment ───────────────────────────────────────────
SNS_ALERT_ARN="${SNS_ALERT_ARN:-}"
ALB_SUFFIX="${ALB_SUFFIX:-}"          # e.g. app/gst-rag-alb/abc123def456  (from ALB ARN)
TG_SUFFIX="${TG_SUFFIX:-}"            # e.g. targetgroup/gst-rag-tg/abc123  (from TG ARN)

if [[ -z "$SNS_ALERT_ARN" ]]; then
  echo "ERROR: Set SNS_ALERT_ARN before running this script."
  echo "  export SNS_ALERT_ARN=arn:aws:sns:ap-south-1:446550122628:leta-alerts"
  exit 1
fi

alarm() {
  local name="$1"; shift
  echo "→ Creating/updating alarm: $name"
  aws cloudwatch put-metric-alarm \
    --region "$REGION" \
    --alarm-actions "$SNS_ALERT_ARN" \
    --ok-actions    "$SNS_ALERT_ARN" \
    --alarm-name    "$name" \
    "$@"
}

# ── 1. ECS CPU utilisation > 80% for 2 consecutive minutes ───────────────────
alarm "leta-ecs-cpu-high" \
  --namespace "AWS/ECS" \
  --metric-name CPUUtilization \
  --dimensions Name=ClusterName,Value="$CLUSTER" Name=ServiceName,Value="$SERVICE" \
  --statistic Average \
  --period 60 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --alarm-description "LETA ECS CPU > 80% — consider scaling out"

# ── 2. ECS Memory utilisation > 85% for 2 consecutive minutes ────────────────
alarm "leta-ecs-memory-high" \
  --namespace "AWS/ECS" \
  --metric-name MemoryUtilization \
  --dimensions Name=ClusterName,Value="$CLUSTER" Name=ServiceName,Value="$SERVICE" \
  --statistic Average \
  --period 60 \
  --evaluation-periods 2 \
  --threshold 85 \
  --comparison-operator GreaterThanThreshold \
  --alarm-description "LETA ECS Memory > 85% — FAISS index or embedding model growing"

# ── 3. ALB UnHealthyHostCount > 0 for 1 minute ───────────────────────────────
if [[ -n "$ALB_SUFFIX" && -n "$TG_SUFFIX" ]]; then
  alarm "leta-alb-unhealthy-host" \
    --namespace "AWS/ApplicationELB" \
    --metric-name UnHealthyHostCount \
    --dimensions \
      Name=LoadBalancer,Value="$ALB_SUFFIX" \
      Name=TargetGroup,Value="$TG_SUFFIX" \
    --statistic Minimum \
    --period 60 \
    --evaluation-periods 1 \
    --threshold 0 \
    --comparison-operator GreaterThanThreshold \
    --alarm-description "LETA ALB has unhealthy targets — ECS task likely crashed or /api/health failing"
else
  echo "⚠  Skipping ALB alarm — set ALB_SUFFIX and TG_SUFFIX to enable."
  echo "   Find them in the ALB and Target Group ARNs in the AWS console."
fi

# ── 4. ALB 5xx error rate > 5% of requests for 3 minutes ────────────────────
if [[ -n "$ALB_SUFFIX" ]]; then
  # Uses math expression: HTTPCode_Target_5XX_Count / RequestCount
  aws cloudwatch put-metric-alarm \
    --region "$REGION" \
    --alarm-name "leta-alb-5xx-rate" \
    --alarm-description "LETA backend 5xx rate > 5% for 3min — likely crash or unhandled exception" \
    --metrics '[
      {"Id":"m1","MetricStat":{"Metric":{"Namespace":"AWS/ApplicationELB","MetricName":"HTTPCode_Target_5XX_Count","Dimensions":[{"Name":"LoadBalancer","Value":"'"$ALB_SUFFIX"'"}]},"Period":60,"Stat":"Sum"},"ReturnData":false},
      {"Id":"m2","MetricStat":{"Metric":{"Namespace":"AWS/ApplicationELB","MetricName":"RequestCount","Dimensions":[{"Name":"LoadBalancer","Value":"'"$ALB_SUFFIX"'"}]},"Period":60,"Stat":"Sum"},"ReturnData":false},
      {"Id":"e1","Expression":"m1/m2","Label":"5xxRate","ReturnData":true}
    ]' \
    --comparison-operator GreaterThanThreshold \
    --threshold 0.05 \
    --evaluation-periods 3 \
    --treat-missing-data notBreaching \
    --alarm-actions "$SNS_ALERT_ARN" \
    --ok-actions    "$SNS_ALERT_ARN"
else
  echo "⚠  Skipping 5xx-rate alarm — set ALB_SUFFIX to enable."
fi

# ── 5. ECS running task count < desired count (task crash loop) ───────────────
alarm "leta-ecs-task-count-low" \
  --namespace "ECS/ContainerInsights" \
  --metric-name RunningTaskCount \
  --dimensions Name=ClusterName,Value="$CLUSTER" Name=ServiceName,Value="$SERVICE" \
  --statistic Minimum \
  --period 60 \
  --evaluation-periods 2 \
  --threshold 1 \
  --comparison-operator LessThanThreshold \
  --alarm-description "LETA ECS running task count < 1 — service is completely down"

echo ""
echo "✓ CloudWatch alarms configured."
echo "  View them at: https://ap-south-1.console.aws.amazon.com/cloudwatch/home?region=ap-south-1#alarmsV2:"
