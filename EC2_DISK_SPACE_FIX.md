# EC2 Disk Space Issue Fix Guide

## Problem
```
ERROR: Could not install packages due to an OSError: [Errno 28] No space left on device
```

This error occurs when your EC2 instance runs out of disk space during the Docker build process.

## Root Causes
1. **Docker build cache** - Accumulated layers from previous builds
2. **Unused Docker images** - Old images not removed after updates
3. **System logs** - Journal logs growing over time
4. **Package manager cache** - APT/YUM cache taking up space
5. **Temporary files** - Un cleaned temporary files

## Solution 1: Run Cleanup Script (Recommended)

### Upload and Run Cleanup Script
```bash
# Connect to your EC2 instance
ssh -i "dev-ankit-key.pem" ec2-user@ec2-13-49-158-58.eu-north-1.compute.amazonaws.com

# Navigate to the project directory
cd ytnotesmaker

# Make the cleanup script executable
chmod +x scripts/cleanup-disk-space.sh

# Run the cleanup script
./scripts/cleanup-disk-space.sh
```

The script will:
- Remove stopped Docker containers
- Remove unused Docker images
- Remove unused Docker volumes
- Remove Docker build cache
- Clean package manager cache
- Clean system logs
- Clean temporary files

## Solution 2: Manual Cleanup Steps

### Step 1: Check Current Disk Usage
```bash
df -h /
```

### Step 2: Clean Docker Space
```bash
# Remove stopped containers
docker container prune -f

# Remove unused images
docker image prune -a -f

# Remove unused volumes
docker volume prune -f

# Remove build cache
docker builder prune -a -f

# Check Docker space usage
docker system df
```

### Step 3: Clean System Space
```bash
# Clean package manager cache (Ubuntu/Debian)
sudo apt-get clean -y
sudo apt-get autoremove -y

# Or for Amazon Linux/RHEL
sudo yum clean all -y

# Clean journal logs
sudo journalctl --vacuum-time=7d

# Clean temporary files
sudo rm -rf /tmp/*
```

### Step 4: Clean Docker Overlay2 (if needed)
```bash
sudo rm -rf /var/lib/docker/overlay2/*-*/merged/tmp/*
```

## Solution 3: Optimize Dockerfile

The backend Dockerfile has been optimized to reduce disk space usage:

1. **Added pip cache purge** - Removes pip cache after installation
2. **Double --no-cache-dir** - Ensures no cache is created during pip install
3. **Clean up build artifacts** - Removes temporary files during build

The updated Dockerfile is already committed to the repository.

## Solution 4: Expand EBS Volume (If Needed)

If you consistently run out of space, consider expanding your EBS volume:

### Option A: Extend Current Volume
```bash
# 1. Go to AWS Console → EC2 → Volumes
# 2. Select your volume and choose "Actions → Modify Volume"
# 3. Increase the size (e.g., from 20GB to 30GB)
# 4. Connect to EC2 and extend the filesystem

# On EC2:
# For ext4 filesystem:
sudo growpart /dev/xvda 1
sudo resize2fs /dev/xvda1

# For xfs filesystem:
sudo xfs_growfs /
```

### Option B: Add New Volume
```bash
# 1. Create new EBS volume in AWS Console
# 2. Attach to EC2 instance
# 3. Format and mount the new volume

sudo mkfs -t ext4 /dev/xvdg
sudo mkdir /mnt/data
sudo mount /dev/xvdg /mnt/data

# Move Docker data directory to new volume
sudo systemctl stop docker
sudo mv /var/lib/docker /mnt/data/
sudo ln -s /mnt/data/docker /var/lib/docker
sudo systemctl start docker
```

## Solution 5: Use Docker Multi-Stage Build (Advanced)

For even more space efficiency, you could implement multi-stage builds, but this requires significant refactoring of the Dockerfile.

## Prevention

### Regular Maintenance
```bash
# Add to crontab for regular cleanup
crontab -e

# Add this line to run cleanup weekly
0 3 * * 0 /path/to/cleanup-disk-space.sh
```

### Monitor Disk Space
```bash
# Check disk usage regularly
df -h

# Set up disk space monitoring
# Consider using AWS CloudWatch metrics
```

### Use Docker Compose Down When Not Needed
```bash
# When not using the application, stop containers
docker-compose down

# Only start when needed
docker-compose up -d
```

## Verification Steps

After cleanup, verify you have enough space:

```bash
# Check disk space (should have at least 5GB free)
df -h /

# Check Docker space
docker system df

# Try building again
docker-compose up -d --build
```

## Troubleshooting

### If Cleanup Script Fails
1. Run each command manually from the script
2. Check for permission issues (use sudo)
3. Check if Docker daemon is running

### If Still Out of Space After Cleanup
1. Expand EBS volume (Solution 4)
2. Move to larger EC2 instance type
3. Remove unnecessary applications from EC2

### If Build Fails Again
1. Check individual image sizes
2. Reduce pip dependencies in req.txt
3. Use smaller base Docker images (alpine vs slim)

## Quick Reference Commands

```bash
# Check disk space
df -h

# Docker cleanup
docker system prune -a --volumes -f

# System cleanup (Ubuntu)
sudo apt-get clean && sudo apt-get autoremove -y

# Clean logs
sudo journalctl --vacuum-time=7d

# Build after cleanup
docker-compose up -d --build
```

## Additional Resources

- [AWS EBS Volume Management](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-changing-volume-size.html)
- [Docker Disk Space Management](https://docs.docker.com/config/pruning/)
- [Linux Disk Space Management](https://www.linux.com/training-tutorials/4-ways-check-disk-space-linux/)