#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ONE-TIME AWS setup script for GST-RAG deployment
# Run this ONCE from your local machine (AWS CLI must be configured).
# Replace every ALL_CAPS placeholder before running.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REGION="ap-south-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="gst-rag-backend"
CLUSTER="gst-rag-cluster"
S3_FRONTEND_BUCKET="gst-rag-frontend-${ACCOUNT_ID}"
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

# ── 3. S3 frontend bucket (static site) ───────────────────────────────────────
echo "→ Creating S3 frontend bucket..."
aws s3 mb s3://$S3_FRONTEND_BUCKET --region $REGION 2>/dev/null || echo "Frontend bucket already exists."
aws s3api put-public-access-block \
  --bucket $S3_FRONTEND_BUCKET \
  --public-access-block-configuration \
    BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false
aws s3api put-bucket-policy \
  --bucket $S3_FRONTEND_BUCKET \
  --policy "{
    \"Version\":\"2012-10-17\",
    \"Statement\":[{
      \"Sid\":\"PublicReadGetObject\",
      \"Effect\":\"Allow\",
      \"Principal\":\"*\",
      \"Action\":\"s3:GetObject\",
      \"Resource\":\"arn:aws:s3:::$S3_FRONTEND_BUCKET/*\"
    }]
  }"
aws s3 website s3://$S3_FRONTEND_BUCKET \
  --index-document index.html \
  --error-document index.html

# ── 4. CloudFront distribution ─────────────────────────────────────────────────
echo "→ Creating CloudFront distribution (this takes ~5 min to deploy)..."
CF_ORIGIN="${S3_FRONTEND_BUCKET}.s3-website.${REGION}.amazonaws.com"
CF_DIST_ID=$(aws cloudfront create-distribution \
  --distribution-config "{
    \"CallerReference\": \"gst-rag-$(date +%s)\",
    \"Origins\": {
      \"Quantity\": 1,
      \"Items\": [{
        \"Id\": \"S3-${S3_FRONTEND_BUCKET}\",
        \"DomainName\": \"${CF_ORIGIN}\",
        \"CustomOriginConfig\": {
          \"HTTPPort\": 80, \"HTTPSPort\": 443,
          \"OriginProtocolPolicy\": \"http-only\"
        }
      }]
    },
    \"DefaultCacheBehavior\": {
      \"TargetOriginId\": \"S3-${S3_FRONTEND_BUCKET}\",
      \"ViewerProtocolPolicy\": \"redirect-to-https\",
      \"AllowedMethods\": {\"Quantity\":2,\"Items\":[\"GET\",\"HEAD\"]},
      \"ForwardedValues\": {\"QueryString\":false,\"Cookies\":{\"Forward\":\"none\"}},
      \"Compress\": true,
      \"DefaultTTL\": 86400
    },
    \"CustomErrorResponses\": {
      \"Quantity\": 1,
      \"Items\": [{
        \"ErrorCode\": 404,
        \"ResponsePagePath\": \"/index.html\",
        \"ResponseCode\": \"200\",
        \"ErrorCachingMinTTL\": 0
      }]
    },
    \"Comment\": \"GST RAG Frontend\",
    \"Enabled\": true,
    \"DefaultRootObject\": \"index.html\"
  }" \
  --query "Distribution.Id" --output text)

echo "CloudFront Distribution ID: $CF_DIST_ID"
CF_DOMAIN=$(aws cloudfront get-distribution --id $CF_DIST_ID \
  --query "Distribution.DomainName" --output text)
echo "Frontend URL: https://$CF_DOMAIN"

# ── 5. ECS Cluster ─────────────────────────────────────────────────────────────
echo "→ Creating ECS cluster..."
aws ecs create-cluster \
  --cluster-name $CLUSTER \
  --capacity-providers FARGATE FARGATE_SPOT \
  2>/dev/null || echo "Cluster already exists."

# ── 6. CloudWatch log group ────────────────────────────────────────────────────
echo "→ Creating CloudWatch log group..."
aws logs create-log-group \
  --log-group-name /ecs/gst-rag-backend \
  --region $REGION \
  2>/dev/null || echo "Log group already exists."
aws logs put-retention-policy \
  --log-group-name /ecs/gst-rag-backend \
  --retention-in-days 30

# ── 7. SSM Parameter Store secrets ────────────────────────────────────────────
echo "→ Storing secrets in SSM Parameter Store..."
echo "Fill in your actual values below, then uncomment and run:"
echo ""
echo "  aws ssm put-parameter --name /gst-rag/ANTHROPIC_API_KEY   --type SecureString --value 'sk-ant-...' --region $REGION"
echo "  aws ssm put-parameter --name /gst-rag/MONGO_URI            --type SecureString --value 'mongodb+srv://...' --region $REGION"
echo "  aws ssm put-parameter --name /gst-rag/SECRET_KEY           --type SecureString --value '$(openssl rand -hex 32)' --region $REGION"
echo "  aws ssm put-parameter --name /gst-rag/ADMIN_MASTER_SECRET  --type SecureString --value '$(openssl rand -hex 32)' --region $REGION"
echo "  aws ssm put-parameter --name /gst-rag/S3_DATA_BUCKET       --type String       --value '$S3_DATA_BUCKET' --region $REGION"
echo "  aws ssm put-parameter --name /gst-rag/ALLOWED_ORIGINS      --type String       --value 'https://$CF_DOMAIN' --region $REGION"

# ── 8. IAM roles ───────────────────────────────────────────────────────────────
echo "→ Creating IAM roles..."

# Execution role (ECS pulls image + reads secrets)
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

# Task role (app reads from S3)
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

# ── 9. IAM user for GitHub Actions ────────────────────────────────────────────
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
      {\"Effect\":\"Allow\",\"Action\":[\"iam:PassRole\"],\"Resource\":[\"arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole\",\"arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskRole\"]},
      {\"Effect\":\"Allow\",\"Action\":[\"s3:PutObject\",\"s3:DeleteObject\",\"s3:ListBucket\"],\"Resource\":[\"arn:aws:s3:::${S3_FRONTEND_BUCKET}\",\"arn:aws:s3:::${S3_FRONTEND_BUCKET}/*\"]},
      {\"Effect\":\"Allow\",\"Action\":[\"cloudfront:CreateInvalidation\"],\"Resource\":\"*\"}
    ]
  }"

KEYS=$(aws iam create-access-key --user-name github-actions-gst-rag 2>/dev/null || echo "{}")
echo ""
echo "═══════════════════════════════════════════════════════"
echo "GitHub Actions Secrets — add these to your repo:"
echo "═══════════════════════════════════════════════════════"
echo "AWS_ACCESS_KEY_ID:          $(echo $KEYS | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get(\"AccessKey\",{}).get(\"AccessKeyId\",\"(run manually)\"))' 2>/dev/null)"
echo "AWS_SECRET_ACCESS_KEY:      (shown once — check AWS console)"
echo "S3_BUCKET:                  $S3_FRONTEND_BUCKET"
echo "CLOUDFRONT_DISTRIBUTION_ID: $CF_DIST_ID"
echo "VITE_API_URL:               https://YOUR_ALB_OR_DOMAIN/  (fill after ALB is created)"
echo ""
echo "Still to do manually (needs VPC + subnets):"
echo "  1. Create ALB → Target Group pointing to ECS service on port 8080"
echo "  2. Register task definition: aws ecs register-task-definition --cli-input-json file://infra/ecs-task-definition.json"
echo "  3. Create ECS service:"
echo "     aws ecs create-service \\"
echo "       --cluster $CLUSTER \\"
echo "       --service-name gst-rag-backend-service \\"
echo "       --task-definition gst-rag-backend \\"
echo "       --desired-count 1 \\"
echo "       --launch-type FARGATE \\"
echo "       --network-configuration 'awsvpcConfiguration={subnets=[YOUR_SUBNET_IDS],securityGroups=[YOUR_SG_ID],assignPublicIp=ENABLED}' \\"
echo "       --load-balancers 'targetGroupArn=YOUR_TG_ARN,containerName=gst-rag-backend,containerPort=8080'"
echo "═══════════════════════════════════════════════════════"
