#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# scripts/setup-aws-ec2.sh
# Automated EC2 setup optimized for AWS t3.micro (Free Tier - 1GB RAM)
# 1. Adds 4GB Swap space (crucial for t3.micro memory stability)
# 2. Installs Docker & Docker Compose
# ─────────────────────────────────────────────────────────────────
set -e

echo "=== 1/3 Configuring 4GB Swap Memory for t3.micro ==="
if [ ! -f /swapfile ]; then
    sudo fallocate -l 4G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
    echo "Swap created successfully!"
else
    echo "Swap file already exists."
fi

echo "=== 2/3 Installing Docker & Prerequisites ==="
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
fi

if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg git
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
elif [ "$OS" = "amzn" ]; then
    sudo dnf update -y
    sudo dnf install -y docker git
    sudo systemctl enable --now docker
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

sudo usermod -aG docker $USER

echo "=== 3/3 Setup Complete! ==="
docker --version
docker compose version || docker-compose --version
free -h
