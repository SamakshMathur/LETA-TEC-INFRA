#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ONE-TIME AWS setup script for GST-RAG deployment
# Run this ONCE from your local machine (AWS CLI must be configured).
# Frontend is deployed via AWS Amplify — this script sets up backend infra only.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REGION="ap-south-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="gst-rag-backend"
CLUSTER="gst-rag-cluster"
S3_DATA_BUCKET="gst-rag-data-${ACCOUNT_ID}"

echo "Account: $ACCOUNT_ID  |  Region: $REGION"

# ── 1. ECR repository ─────────────────────────────────────────────────────────
echo "→ Creating ECR repository..."
aws ecr create-repository \
  --repository-name $ECR_REPO \
  --region $REGION \
  --image-scanning-configuration scanOnPush=true \
  --image-tag-mutability MUTABLE \
  2>/dev/null || echo "ECR repo already exists."

# ── 2. S3 data bucket (vector index + chunks) ─────────────────────────────────
echo "→ Creating S3 data bucket..."
aws s3 mb s3://$S3_DATA_BUCKET --region $REGION 2>/dev/null || echo "Data bucket already exists."
aws s3api put-bucket-versioning \
  --bucket $S3_DATA_BUCKET \
  --versioning-configuration Status=Enabled

echo ""
echo "IMPORTANT: Upload your vector data to S3 now:"
echo "  aws s3 cp rag-backend/vectordb/index.faiss      s3://$S3_DATA_BUCKET/vectordb/index.faiss"
echo "  aws s3 cp rag-backend/data/chunks/chunks.jsonl  s3://$S3_DATA_BUCKET/data/chunks/chunks.jsonl"
echo "  aws s3 cp rag-backend/RAG_INFORMATION_DATABASE/ s3://$S3_DATA_BUCKET/RAG_INFORMATION_DATABASE/ --recursive"
echo ""

# ── 3. ECS Cluster ─────────────────────────────────────────────────────────────
echo "→ Creating ECS cluster..."
aws ecs create-cluster \
  --cluster-name $CLUSTER \
  --capacity-providers FARGATE FARGATE_SPOT \
  2>/dev/null || echo "Cluster already exists."

# ── 4. CloudWatch log group ────────────────────────────────────────────────────
echo "→ Creating CloudWatch log group..."
aws logs create-log-group \
  --log-group-name /ecs/gst-rag-backend \
  --region $REGION \
  2>/dev/null || echo "Log group already exists."
aws logs put-retention-policy \
  --log-group-name /ecs/gst-rag-backend \
  --retention-in-days 30

# ── 5. SSM Parameter Store secrets ────────────────────────────────────────────
echo ""
echo "→ Store your secrets in SSM (fill in real values and run these):"
echo ""
echo "  aws ssm put-parameter --name /gst-rag/ANTHROPIC_API_KEY   --type SecureString --value 'sk-ant-...'                       --region $REGION"
echo "  aws ssm put-parameter --name /gst-rag/MONGO_URI            --type SecureString --value 'mongodb+srv://...'                --region $REGION"
echo "  aws ssm put-parameter --name /gst-rag/SECRET_KEY           --type SecureString --value \"\$(openssl rand -hex 32)\"         --region $REGION"
echo "  aws ssm put-parameter --name /gst-rag/ADMIN_MASTER_SECRET  --type SecureString --value \"\$(openssl rand -hex 32)\"         --region $REGION"
echo "  aws ssm put-parameter --name /gst-rag/S3_DATA_BUCKET       --type String       --value '$S3_DATA_BUCKET'                  --region $REGION"
echo "  aws ssm put-parameter --name /gst-rag/ALLOWED_ORIGINS      --type String       --value 'https://YOUR_AMPLIFY_URL'         --region $REGION"

# ── 6. IAM roles ───────────────────────────────────────────────────────────────
echo ""
echo "→ Creating IAM roles..."

# Execution role (ECS pulls image + reads secrets from SSM)
aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  2>/dev/null || true
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
aws iam put-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-name SSMParameterAccess \
  --policy-document "{
    \"Version\":\"2012-10-17\",
    \"Statement\":[{
      \"Effect\":\"Allow\",
      \"Action\":[\"ssm:GetParameters\",\"ssm:GetParameter\"],
      \"Resource\":\"arn:aws:ssm:${REGION}:${ACCOUNT_ID}:parameter/gst-rag/*\"
    }]
  }"

# Task role (app reads data files from S3)
aws iam create-role \
  --role-name ecsTaskRole \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  2>/dev/null || true
aws iam put-role-policy \
  --role-name ecsTaskRole \
  --policy-name S3DataAccess \
  --policy-document "{
    \"Version\":\"2012-10-17\",
    \"Statement\":[{
      \"Effect\":\"Allow\",
      \"Action\":[\"s3:GetObject\",\"s3:ListBucket\"],
      \"Resource\":[
        \"arn:aws:s3:::${S3_DATA_BUCKET}\",
        \"arn:aws:s3:::${S3_DATA_BUCKET}/*\"
      ]
    }]
  }"

# ── 7. IAM user for GitHub Actions ────────────────────────────────────────────
echo "→ Creating GitHub Actions deploy user..."
aws iam create-user --user-name github-actions-gst-rag 2>/dev/null || true
aws iam put-user-policy \
  --user-name github-actions-gst-rag \
  --policy-name DeployPolicy \
  --policy-document "{
    \"Version\":\"2012-10-17\",
    \"Statement\":[
      {\"Effect\":\"Allow\",\"Action\":[\"ecr:*\"],\"Resource\":\"arn:aws:ecr:${REGION}:${ACCOUNT_ID}:repository/${ECR_REPO}\"},
      {\"Effect\":\"Allow\",\"Action\":[\"ecr:GetAuthorizationToken\"],\"Resource\":\"*\"},
      {\"Effect\":\"Allow\",\"Action\":[\"ecs:RegisterTaskDefinition\",\"ecs:UpdateService\",\"ecs:DescribeServices\",\"ecs:DescribeTaskDefinition\",\"ecs:ListTaskDefinitions\"],\"Resource\":\"*\"},
      {\"Effect\":\"Allow\",\"Action\":[\"iam:PassRole\"],\"Resource\":[
        \"arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole\",
        \"arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskRole\"
      ]}
    ]
  }"

KEYS=$(aws iam create-access-key --user-name github-actions-gst-rag 2>/dev/null || echo "{}")

echo ""
echo "═══════════════════════════════════════════════════════"
echo "GitHub Actions Secrets — add these to your repo:"
echo "═══════════════════════════════════════════════════════"
echo "AWS_ACCESS_KEY_ID:      $(echo $KEYS | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get(\"AccessKey\",{}).get(\"AccessKeyId\",\"(run manually)\"))' 2>/dev/null)"
echo "AWS_SECRET_ACCESS_KEY:  (shown once — check IAM console → Users → github-actions-gst-rag → Security credentials)"
echo ""
echo "Next step — run the backend deploy script:"
echo "  bash infra/register-backend.sh"
echo "═══════════════════════════════════════════════════════"
