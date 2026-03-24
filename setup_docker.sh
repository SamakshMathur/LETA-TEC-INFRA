#!/bin/bash
set -e

# Update and install Docker
sudo apt-get update
sudo apt-get install -y docker.io git

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add current user to docker group
sudo usermod -aG docker $USER

echo "Docker installed successfully! Please log out and log back in for group changes to take effect."
