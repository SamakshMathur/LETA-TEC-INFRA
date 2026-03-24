#!/bin/bash

# 1. FIX CRASHING: Add 4GB Swap Space
echo "🛠️  Checking Swap Space..."
if [ $(swapon --show | wc -l) -eq 0 ]; then
    echo "⚠️  No swap detected. Creating 4GB swap file to prevent crashes..."
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "✅ Swap created! Memory stability improved."
else
    echo "✅ Swap already active."
fi

# 2. Update Code
echo "⬇️  Pulling latest code..."
git reset --hard
git pull origin main

# 3. Docker Maintenance
echo "🐳 Pruning old Docker images & volumes (Aggressive Cleanup)..."
sudo docker system prune -a -f --volumes

# 4. Build & Run
echo "🚀 Building Backend (Lightweight)..."
sudo docker build -t rag-backend .

echo "🔥 Starting Container..."
# Stop old container if running
sudo docker stop rag-backend || true
sudo docker rm rag-backend || true

# Run new container with restart policy AND MOUNTED VOLUMES
# We mount the local data folders into the container so they are accessible
# without being built INTO the image.
sudo docker run -d \
  --name rag-backend \
  -p 8000:8000 \
  --restart always \
  --env-file .env \
  -v "$(pwd)/RAG_INFORMATION_DATABASE:/app/RAG_INFORMATION_DATABASE" \
  -v "$(pwd)/vectordb:/app/vectordb" \
  rag-backend

echo "✅ Deployment Complete! Backend is running on port 8000."
