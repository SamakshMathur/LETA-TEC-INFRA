#!/usr/bin/env bash
# Watches contextual_rebuild.log and restarts ECS the moment it finishes.
# Run alongside the rebuild:
#   bash scripts/watch_and_restart_ecs.sh

LOG="logs/contextual_rebuild.log"
CLUSTER="gst-rag-cluster"
SERVICE="gst-rag-backend-service"
REGION="ap-south-1"

echo "[watcher] Watching $LOG for completion..."

while true; do
    if [ -f "$LOG" ]; then
        if grep -q "ALL PHASES COMPLETE" "$LOG"; then
            echo "[watcher] ✓ Rebuild complete — forcing ECS service restart..."
            aws ecs update-service \
                --cluster "$CLUSTER" \
                --service "$SERVICE" \
                --force-new-deployment \
                --region "$REGION" \
                --output text \
                --query "service.serviceName"
            echo "[watcher] ECS restart triggered. New task will pull fresh FAISS from S3."
            exit 0
        fi
        if grep -q "ERROR\|FAILED\|Traceback" "$LOG" | tail -5; then
            echo "[watcher] ⚠ Errors detected in log — check logs/contextual_rebuild.log"
        fi
    fi
    sleep 60
done
