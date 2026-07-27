$ErrorActionPreference = "Stop"

$REGION = "ap-south-1"
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$ECR_REPO = "gst-rag-backend"
$CLUSTER = "gst-rag-cluster"
$S3_DATA_BUCKET = "gst-rag-data-$ACCOUNT_ID"

Write-Host "Account: $ACCOUNT_ID  |  Region: $REGION"

# 1. ECR repository
Write-Host "`n-> Creating ECR repository..."
try { aws ecr create-repository --repository-name $ECR_REPO --region $REGION --image-scanning-configuration scanOnPush=true --image-tag-mutability MUTABLE | Out-Null } catch { Write-Host "ECR repo already exists." }

# 2. S3 data bucket
Write-Host "-> Creating S3 data bucket..."
try { aws s3 mb "s3://$S3_DATA_BUCKET" --region $REGION | Out-Null } catch { Write-Host "Data bucket already exists." }
aws s3api put-bucket-versioning --bucket $S3_DATA_BUCKET --versioning-configuration Status=Enabled

Write-Host "`nIMPORTANT: Upload your vector data to S3 after this script:"
Write-Host "  aws s3 cp rag-backend/vectordb/ s3://$S3_DATA_BUCKET/vectordb/ --recursive"
Write-Host "  aws s3 cp rag-backend/data/chunks/ s3://$S3_DATA_BUCKET/data/chunks/ --recursive"

# 3. ECS Cluster
Write-Host "`n-> Creating ECS cluster..."
try { aws ecs create-cluster --cluster-name $CLUSTER --capacity-providers FARGATE FARGATE_SPOT | Out-Null } catch { Write-Host "Cluster already exists." }

# 4. CloudWatch log group
Write-Host "-> Creating CloudWatch log group..."
try { aws logs create-log-group --log-group-name /ecs/gst-rag-backend --region $REGION | Out-Null } catch { Write-Host "Log group already exists." }
aws logs put-retention-policy --log-group-name /ecs/gst-rag-backend --retention-in-days 30

# 5. IAM execution role
Write-Host "-> Creating IAM roles..."
$trustPolicy = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
try { aws iam create-role --role-name ecsTaskExecutionRole --assume-role-policy-document $trustPolicy | Out-Null } catch {}
aws iam attach-role-policy --role-name ecsTaskExecutionRole --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
$ssmPolicy = "{`"Version`":`"2012-10-17`",`"Statement`":[{`"Effect`":`"Allow`",`"Action`":[`"ssm:GetParameters`",`"ssm:GetParameter`"],`"Resource`":`"arn:aws:ssm:${REGION}:${ACCOUNT_ID}:parameter/gst-rag/*`"}]}"
aws iam put-role-policy --role-name ecsTaskExecutionRole --policy-name SSMParameterAccess --policy-document $ssmPolicy

# IAM task role
try { aws iam create-role --role-name ecsTaskRole --assume-role-policy-document $trustPolicy | Out-Null } catch {}
$s3Policy = "{`"Version`":`"2012-10-17`",`"Statement`":[{`"Effect`":`"Allow`",`"Action`":[`"s3:GetObject`",`"s3:ListBucket`"],`"Resource`":[`"arn:aws:s3:::${S3_DATA_BUCKET}`",`"arn:aws:s3:::${S3_DATA_BUCKET}/*`"]}]}"
aws iam put-role-policy --role-name ecsTaskRole --policy-name S3DataAccess --policy-document $s3Policy

# 6. GitHub Actions IAM user
Write-Host "-> Creating GitHub Actions deploy user..."
try { aws iam create-user --user-name github-actions-gst-rag | Out-Null } catch {}
$deployPolicy = "{`"Version`":`"2012-10-17`",`"Statement`":[{`"Effect`":`"Allow`",`"Action`":[`"ecr:*`"],`"Resource`":`"arn:aws:ecr:${REGION}:${ACCOUNT_ID}:repository/${ECR_REPO}`"},{`"Effect`":`"Allow`",`"Action`":[`"ecr:GetAuthorizationToken`"],`"Resource`":`"*`"},{`"Effect`":`"Allow`",`"Action`":[`"ecs:RegisterTaskDefinition`",`"ecs:UpdateService`",`"ecs:DescribeServices`",`"ecs:DescribeTaskDefinition`",`"ecs:ListTaskDefinitions`"],`"Resource`":`"*`"},{`"Effect`":`"Allow`",`"Action`":[`"iam:PassRole`"],`"Resource`":[`"arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole`",`"arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskRole`"]}]}"
aws iam put-user-policy --user-name github-actions-gst-rag --policy-name DeployPolicy --policy-document $deployPolicy

$keys = aws iam create-access-key --user-name github-actions-gst-rag | ConvertFrom-Json

Write-Host "`n======================================================="
Write-Host "GitHub Actions Secrets - add these to your repo:"
Write-Host "======================================================="
Write-Host "AWS_ACCESS_KEY_ID:     $($keys.AccessKey.AccessKeyId)"
Write-Host "AWS_SECRET_ACCESS_KEY: $($keys.AccessKey.SecretAccessKey)"
Write-Host "`nNext: run .\infra\register-backend.ps1"
Write-Host "======================================================="
