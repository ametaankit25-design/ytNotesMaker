#!/bin/bash
# EC2 Disk Space Cleanup Script for ytNotesMaker
# This script helps free up disk space on EC2 instances

set -e

echo "=========================================="
echo "EC2 Disk Space Cleanup Tool"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check current disk usage
echo "1. Current Disk Usage:"
df -h /

echo ""
echo "2. Docker Disk Usage:"
docker system df 2>/dev/null || echo "Docker not running or not installed"

echo ""
echo "=========================================="
echo "Cleaning Docker Space"
echo "=========================================="

# Remove stopped containers
echo ""
echo "3. Removing stopped Docker containers..."
CONTAINERS_REMOVED=$(docker container prune -f 2>/dev/null || echo "0")
print_status 0 "Stopped containers removed"

# Remove unused images
echo ""
echo "4. Removing unused Docker images..."
docker image prune -a -f 2>/dev/null || print_warning "Could not prune images"
print_status 0 "Unused images removed"

# Remove unused volumes
echo ""
echo "5. Removing unused Docker volumes..."
docker volume prune -f 2>/dev/null || print_warning "Could not prune volumes"
print_status 0 "Unused volumes removed"

# Remove build cache
echo ""
echo "6. Removing Docker build cache..."
docker builder prune -a -f 2>/dev/null || print_warning "Could not prune build cache"
print_status 0 "Build cache removed"

# Clean up system
echo ""
echo "=========================================="
echo "Cleaning System Space"
echo "=========================================="

# Clean package manager cache
echo ""
echo "7. Cleaning package manager cache..."
if command -v apt-get &> /dev/null; then
    sudo apt-get clean -y
    sudo apt-get autoremove -y
    print_status 0 "APT cache cleaned"
elif command -v yum &> /dev/null; then
    sudo yum clean all -y
    print_status 0 "YUM cache cleaned"
else
    print_warning "Unknown package manager"
fi

# Clean logs
echo ""
echo "8. Cleaning system logs..."
sudo journalctl --vacuum-time=7d 2>/dev/null || print_warning "Could not clean journal logs"
print_status 0 "System logs cleaned"

# Clean temporary files
echo ""
echo "9. Cleaning temporary files..."
sudo rm -rf /tmp/* 2>/dev/null || print_warning "Could not clean /tmp"
print_status 0 "Temporary files cleaned"

# Clean Docker overlay2 (if exists)
echo ""
echo "10. Cleaning Docker overlay2 directory..."
sudo rm -rf /var/lib/docker/overlay2/*-*/merged/tmp/* 2>/dev/null || print_warning "Could not clean overlay2"
print_status 0 "Docker overlay2 cleaned"

# Display final disk usage
echo ""
echo "=========================================="
echo "Final Disk Usage"
echo "=========================================="
df -h /

echo ""
echo "=========================================="
echo "Docker Space After Cleanup"
echo "=========================================="
docker system df 2>/dev/null || echo "Docker not running or not installed"

echo ""
echo "=========================================="
echo "Cleanup Complete"
echo "=========================================="
echo ""
echo "Recommended next steps:"
echo "1. Try building again: docker-compose up -d --build"
echo "2. If still failing, consider expanding EBS volume"
echo "3. Monitor disk usage regularly: df -h"
echo ""