$ErrorActionPreference = "Stop"

$REGION      = "ap-south-1"
$CLUSTER     = "gst-rag-cluster"
$SERVICE     = "gst-rag-backend-service"
$TASK_FAMILY = "gst-rag-backend"
$ACCOUNT_ID  = (aws sts get-caller-identity --query Account --output text)

Write-Host "Account: $ACCOUNT_ID  |  Region: $REGION"

# 1. Substitute account ID in task definition — write WITHOUT BOM
$taskDefPath    = Join-Path $PSScriptRoot "ecs-task-definition.json"
$taskDefContent = (Get-Content $taskDefPath -Raw) -replace "YOUR_ACCOUNT_ID", $ACCOUNT_ID
$tmpFile        = Join-Path $env:TEMP "task-def-ready.json"
$utf8NoBom      = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($tmpFile, $taskDefContent, $utf8NoBom)
$tmpFileForward = $tmpFile -replace "\\", "/"
Write-Host "-> Task definition ready: $tmpFileForward"

# 2. Register task definition
$TASK_DEF_ARN = (aws ecs register-task-definition --cli-input-json "file://$tmpFileForward" --region $REGION --query taskDefinition.taskDefinitionArn --output text)
Write-Host "-> Registered: $TASK_DEF_ARN"

# 3. Discover default VPC and subnets
$DEFAULT_VPC = (aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query Vpcs[0].VpcId --output text --region $REGION)
$RAW_SUBNETS = (aws ec2 describe-subnets --filters "Name=vpc-id,Values=$DEFAULT_VPC" --query "Subnets[*].SubnetId" --output text --region $REGION)
$SUBNET_IDS  = ($RAW_SUBNETS -split "\s+") | Where-Object { $_ -ne "" }
$subnetList  = $SUBNET_IDS -join ","
Write-Host "-> VPC: $DEFAULT_VPC"
Write-Host "-> Subnets: $subnetList"

# 4. Get existing security group
$SG_ID = (aws ec2 describe-security-groups --filters Name=group-name,Values=gst-rag-ecs-sg "Name=vpc-id,Values=$DEFAULT_VPC" --query "SecurityGroups[0].GroupId" --output text --region $REGION 2>$null)
if (-not $SG_ID -or $SG_ID -eq "None") {
    $SG_ID = (aws ec2 create-security-group --group-name gst-rag-ecs-sg --description "GST-RAG ECS tasks" --vpc-id $DEFAULT_VPC --region $REGION --query GroupId --output text)
    aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 8080 --cidr 0.0.0.0/0 --region $REGION | Out-Null
    Write-Host "-> Created security group: $SG_ID"
} else {
    Write-Host "-> Using existing security group: $SG_ID"
}

# 5. Create or update ECS service
$SERVICE_STATUS = "MISSING"
try {
    $SERVICE_STATUS = (aws ecs describe-services --cluster $CLUSTER --services $SERVICE --region $REGION --query "services[0].status" --output text)
} catch { }

if ($SERVICE_STATUS -eq "ACTIVE") {
    Write-Host "-> Service exists - forcing new deployment..."
    aws ecs update-service --cluster $CLUSTER --service $SERVICE --task-definition $TASK_DEF_ARN --force-new-deployment --region $REGION | Out-Null
    Write-Host "-> Rolling deploy triggered."
} else {
    Write-Host "-> Creating ECS service..."
    aws ecs create-service --cluster $CLUSTER --service-name $SERVICE --task-definition $TASK_FAMILY --desired-count 1 --launch-type FARGATE --network-configuration "awsvpcConfiguration={subnets=[$subnetList],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" --region $REGION | Out-Null
    Write-Host "-> Service created."
}

# 6. Wait for public IP
Write-Host ""
Write-Host "Waiting for task to start (up to 3 min)..."
for ($i = 1; $i -le 18; $i++) {
    Start-Sleep -Seconds 10
    $TASK_ARN = ""
    try { $TASK_ARN = (aws ecs list-tasks --cluster $CLUSTER --service-name $SERVICE --desired-status RUNNING --region $REGION --query "taskArns[0]" --output text) } catch { }
    if ($TASK_ARN -and $TASK_ARN -ne "None") {
        $ENI_ID = ""
        try { $ENI_ID = (aws ecs describe-tasks --cluster $CLUSTER --tasks $TASK_ARN --region $REGION --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" --output text) } catch { }
        if ($ENI_ID -and $ENI_ID -ne "None") {
            $PUBLIC_IP = ""
            try { $PUBLIC_IP = (aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --region $REGION --query "NetworkInterfaces[0].Association.PublicIp" --output text) } catch { }
            if ($PUBLIC_IP -and $PUBLIC_IP -ne "None") {
                Write-Host ""
                Write-Host "======================================================="
                Write-Host "Backend starting at:"
                Write-Host "  http://${PUBLIC_IP}:8080/api/health"
                Write-Host ""
                Write-Host "Use this as VITE_API_URL in Amplify."
                Write-Host "Container takes ~3 min to pass health checks."
                Write-Host "======================================================="
                exit 0
            }
        }
    }
    $secs = $i * 10
    Write-Host "  waiting... ($secs s)"
}

Write-Host ""
Write-Host "======================================================="
Write-Host "Task still starting. Check ECS console:"
Write-Host "  https://$REGION.console.aws.amazon.com/ecs/v2/clusters/$CLUSTER/services/$SERVICE"
Write-Host "======================================================="
