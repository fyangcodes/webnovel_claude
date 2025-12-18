#!/bin/bash

# Docker Engine Installation Script for Ubuntu
# This script installs Docker Engine without Docker Desktop

set -e  # Exit on any error

echo "================================================"
echo "Docker Engine Installation Script for Ubuntu"
echo "================================================"
echo ""

# Check if running on Ubuntu
if [ ! -f /etc/lsb-release ]; then
    echo "Error: This script is designed for Ubuntu"
    exit 1
fi

echo "Step 1: Updating package index and installing prerequisites..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

echo ""
echo "Step 2: Adding Docker's official GPG key..."
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo ""
echo "Step 3: Setting up Docker repository..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo ""
echo "Step 4: Installing Docker Engine..."
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo ""
echo "Step 5: Verifying Docker installation..."
sudo docker run hello-world

echo ""
echo "Step 6: Adding current user to docker group (to run without sudo)..."
sudo usermod -aG docker $USER

echo ""
echo "================================================"
echo "Docker Engine installed successfully!"
echo "================================================"
echo ""
echo "IMPORTANT: You need to log out and log back in (or restart)"
echo "for the group changes to take effect."
echo ""
echo "After logging back in, verify with:"
echo "  docker --version"
echo "  docker compose version"
echo "  docker run hello-world"
echo ""
echo "To apply group changes immediately (without logout):"
echo "  newgrp docker"
echo "================================================"
