#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Register ECS task definition and create (or update) the ECS service.
# Run this AFTER aws-setup.sh and after storing SSM secrets.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REGION="ap-south-1"
CLUSTER="gst-rag-cluster"
SERVICE="gst-rag-backend-service"
TASK_FAMILY="gst-rag-backend"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Account: $ACCOUNT_ID  |  Region: $REGION"

# ── 1. Substitute account ID in task definition ───────────────────────────────
sed "s/YOUR_ACCOUNT_ID/$ACCOUNT_ID/g" "$SCRIPT_DIR/ecs-task-definition.json" > /tmp/task-def-ready.json
echo "→ Task definition ready"

# ── 2. Register the task definition ──────────────────────────────────────────
TASK_DEF_ARN=$(aws ecs register-task-definition \
  --cli-input-json file:///tmp/task-def-ready.json \
  --region $REGION \
  --query "taskDefinition.taskDefinitionArn" \
  --output text)
echo "→ Registered: $TASK_DEF_ARN"

# ── 3. Discover default VPC and subnets ───────────────────────────────────────
DEFAULT_VPC=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" --output text --region $REGION)

SUBNET_IDS_RAW=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$DEFAULT_VPC" \
  --query "Subnets[*].SubnetId" --output text --region $REGION)

# Convert tab-separated to JSON array
SUBNET_JSON=$(echo "$SUBNET_IDS_RAW" | python3 -c "
import sys
ids = sys.stdin.read().strip().split()
print('[' + ','.join(f'\"{i}\"' for i in ids) + ']')
")

echo "→ VPC: $DEFAULT_VPC"
echo "→ Subnets: $SUBNET_JSON"

# ── 4. Create ECS security group (if not already present) ────────────────────
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=gst-rag-ecs-sg" "Name=vpc-id,Values=$DEFAULT_VPC" \
  --query "SecurityGroups[0].GroupId" --output text --region $REGION 2>/dev/null || true)

if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  SG_ID=$(aws ec2 create-security-group \
    --group-name gst-rag-ecs-sg \
    --description "GST-RAG ECS tasks" \
    --vpc-id $DEFAULT_VPC \
    --region $REGION \
    --query "GroupId" --output text)

  aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID --protocol tcp --port 8080 --cidr 0.0.0.0/0 \
    --region $REGION

  echo "→ Created security group: $SG_ID"
else
  echo "→ Using existing security group: $SG_ID"
fi

# ── 5. Create or update the ECS service ──────────────────────────────────────
SERVICE_STATUS=$(aws ecs describe-services \
  --cluster $CLUSTER --services $SERVICE --region $REGION \
  --query "services[0].status" --output text 2>/dev/null || echo "MISSING")

if [ "$SERVICE_STATUS" = "ACTIVE" ]; then
  echo "→ Service already exists — forcing new deployment..."
  aws ecs update-service \
    --cluster $CLUSTER \
    --service $SERVICE \
    --task-definition $TASK_DEF_ARN \
    --force-new-deployment \
    --region $REGION > /dev/null
  echo "→ Rolling deploy triggered."
else
  echo "→ Creating ECS service (public IP, no ALB — good for initial testing)..."
  aws ecs create-service \
    --cluster $CLUSTER \
    --service-name $SERVICE \
    --task-definition $TASK_FAMILY \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=$SUBNET_JSON,securityGroups=[\"$SG_ID\"],assignPublicIp=ENABLED}" \
    --region $REGION > /dev/null
  echo "→ Service created."
fi

# ── 6. Get the public IP once the task is running ────────────────────────────
echo ""
echo "Waiting for task to start (up to 3 min)..."
for i in $(seq 1 18); do
  TASK_ARN=$(aws ecs list-tasks \
    --cluster $CLUSTER --service-name $SERVICE \
    --desired-status RUNNING --region $REGION \
    --query "taskArns[0]" --output text 2>/dev/null || true)

  if [ -n "$TASK_ARN" ] && [ "$TASK_ARN" != "None" ]; then
    ENI_ID=$(aws ecs describe-tasks \
      --cluster $CLUSTER --tasks $TASK_ARN --region $REGION \
      --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" \
      --output text 2>/dev/null || true)

    if [ -n "$ENI_ID" ] && [ "$ENI_ID" != "None" ]; then
      PUBLIC_IP=$(aws ec2 describe-network-interfaces \
        --network-interface-ids $ENI_ID --region $REGION \
        --query "NetworkInterfaces[0].Association.PublicIp" --output text 2>/dev/null || true)

      if [ -n "$PUBLIC_IP" ] && [ "$PUBLIC_IP" != "None" ]; then
        echo ""
        echo "═══════════════════════════════════════════════════════"
        echo "Backend is starting at:"
        echo "  http://$PUBLIC_IP:8080/api/health"
        echo ""
        echo "Note: The container takes ~3 min to pass health checks"
        echo "      (downloads embedding model on first start)."
        echo ""
        echo "Once healthy, set ALLOWED_ORIGINS in SSM:"
        echo "  aws ssm put-parameter --name /gst-rag/ALLOWED_ORIGINS \\"
        echo "    --type String --value 'https://YOUR_AMPLIFY_URL' \\"
        echo "    --overwrite --region $REGION"
        echo ""
        echo "ECS Console:"
        echo "  https://${REGION}.console.aws.amazon.com/ecs/v2/clusters/${CLUSTER}/services/${SERVICE}"
        echo "═══════════════════════════════════════════════════════"
        exit 0
      fi
    fi
  fi

  sleep 10
  echo "  waiting... ($((i * 10))s)"
done

echo ""
echo "═══════════════════════════════════════════════════════"
echo "Task is still starting — check ECS console:"
echo "  https://${REGION}.console.aws.amazon.com/ecs/v2/clusters/${CLUSTER}/services/${SERVICE}"
echo "═══════════════════════════════════════════════════════"
