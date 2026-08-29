# LETA Production Rollback Runbook

**When to use this:** A deploy broke production. `/api/health` is failing, users are getting errors, or the CloudWatch `leta-alb-unhealthy-host` alarm fired. You need to roll back to the last known-good ECS task definition within minutes, not hours.

---

## Step 0 — Confirm it's the deploy (< 2 min)

```bash
# Is the health endpoint down?
curl -s -o /dev/null -w "%{http_code}" https://api.letatec.com/api/health

# Which task definition is currently running?
aws ecs describe-services \
  --cluster gst-rag-cluster \
  --services gst-rag-backend-service \
  --region ap-south-1 \
  --query 'services[0].{desired:desiredCount,running:runningCount,taskDef:taskDefinition}'
```

If `running < desired` and health is not 200, proceed.

---

## Step 1 — Find the last good revision (< 1 min)

```bash
# List recent task definition revisions (newest first)
aws ecs list-task-definitions \
  --family-prefix gst-rag-backend \
  --region ap-south-1 \
  --sort DESC \
  --query 'taskDefinitionArns[:10]'
```

The current broken revision is the one at index 0. The good one is index 1 (last deploy before this one). Note its full ARN:

```
arn:aws:ecs:ap-south-1:446550122628:task-definition/gst-rag-backend:NNN
```

Cross-check with GitHub Actions: the commit SHA is in the image tag (ECR). Match `NNN-1` against the previous successful deploy run.

---

## Step 2 — Force the service to run the previous revision (< 2 min)

```bash
GOOD_REVISION="arn:aws:ecs:ap-south-1:446550122628:task-definition/gst-rag-backend:NNN"

aws ecs update-service \
  --cluster gst-rag-cluster \
  --service gst-rag-backend-service \
  --task-definition "$GOOD_REVISION" \
  --desired-count 2 \
  --force-new-deployment \
  --region ap-south-1
```

ECS will drain the broken tasks and start two new ones from the pinned revision. Rolling replacement — zero downtime if at least one old task survives long enough.

---

## Step 3 — Verify recovery (< 3 min)

```bash
# Poll health until 200
for i in $(seq 1 12); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://api.letatec.com/api/health)
  echo "[$(date +%H:%M:%S)] status=$STATUS"
  [ "$STATUS" = "200" ] && echo "✓ Recovered" && break
  sleep 15
done

# Confirm 2 tasks running
aws ecs describe-services \
  --cluster gst-rag-cluster \
  --services gst-rag-backend-service \
  --region ap-south-1 \
  --query 'services[0].{running:runningCount,desired:desiredCount,taskDef:taskDefinition}'
```

---

## Step 4 — Diagnose the broken deploy (after recovery)

```bash
# Fetch recent log events from the broken task
aws logs filter-log-events \
  --log-group-name /ecs/gst-rag-backend \
  --region ap-south-1 \
  --start-time $(date -d '30 minutes ago' +%s000) \
  --filter-pattern "ERROR" \
  --query 'events[*].message' \
  --output text | tail -50
```

Or use CloudWatch Logs Insights:
```
fields @timestamp, @message
| filter @message like /ERROR|Exception|Traceback/
| sort @timestamp desc
| limit 50
```
Run this in the `/ecs/gst-rag-backend` log group for the time window of the broken deploy.

---

## Step 5 — Fix forward, don't leave production pinned

After rollback, production is running an old revision permanently. The deploy workflow will overwrite this on the next push to main. **Fix the root cause first** — use the broken SHA branch, fix it, and let CI + deploy run normally.

To check if production has been accidentally left on the rollback revision after fixes:
```bash
aws ecs describe-services \
  --cluster gst-rag-cluster \
  --services gst-rag-backend-service \
  --region ap-south-1 \
  --query 'services[0].taskDefinition'
```
This should match the latest task definition revision after the next successful deploy.

---

## Quick reference

| Command | Purpose |
|---------|---------|
| `aws ecs list-task-definitions --family-prefix gst-rag-backend --sort DESC` | Find rollback target |
| `aws ecs update-service --task-definition <ARN> --force-new-deployment` | Execute rollback |
| `curl https://api.letatec.com/api/health` | Verify recovery |
| `aws logs filter-log-events --log-group-name /ecs/gst-rag-backend --filter-pattern ERROR` | Diagnose |

**Total time target: under 5 minutes from alarm to recovery.**
