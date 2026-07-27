# Nginx 403 Forbidden Error Fix Guide

## Problem
When accessing the ytNotesMaker application on EC2, you encounter a 403 Forbidden error.

## Root Causes
1. **Nginx buffer size limitations** - Large API responses get truncated
2. **Missing CORS headers** - Cross-origin requests blocked
3. **Missing proxy headers** - Backend rejects requests without proper forwarding info
4. **File permission issues** - Static files cannot be accessed
5. **Client body size limits** - Large requests (like long YouTube URLs) are rejected

## Solution Applied

### Enhanced Nginx Configuration
The `frontend/nginx.conf` file has been updated with:

1. **Increased buffer sizes:**
   ```nginx
   client_body_buffer_size 128k;
   client_max_body_size 10M;
   proxy_buffer_size 128k;
   proxy_buffers 4 256k;
   proxy_busy_buffers_size 256k;
   ```

2. **Additional proxy headers:**
   ```nginx
   proxy_set_header   X-Forwarded-Proto $scheme;
   proxy_set_header   Upgrade $http_upgrade;
   proxy_set_header   Connection "upgrade";
   ```

3. **Error handling:**
   ```nginx
   proxy_intercept_errors on;
   error_page 403 404 500 502 503 504 = /api_error_handler;
   ```

4. **Health check endpoint:**
   ```nginx
   location /health {
       return 200 "healthy\n";
   }
   ```

## Deployment Instructions

### Option 1: Deploy via SSH (Recommended)
```bash
# 1. Connect to your EC2 instance
ssh -i "dev-ankit-key.pem" ec2-user@ec2-13-49-158-58.eu-north-1.compute.amazonaws.com

# 2. Navigate to the project directory
cd ytnotesmaker

# 3. Pull the latest changes
git pull

# 4. Rebuild and restart containers
# Use docker-compose (with hyphen) for older Docker versions:
docker-compose down
docker-compose up -d --build

# OR use docker compose (with space) for newer Docker versions:
# docker compose down
# docker compose up -d --build

# 5. Check the status
docker-compose ps
docker-compose logs -f
```

### Option 2: Manual File Update
If you cannot pull from git, manually update the nginx config:

```bash
# On EC2 server
cd ytnotesmaker/frontend

# Backup the old config
cp nginx.conf nginx.conf.backup

# Edit the file
nano nginx.conf
# Replace the entire content with the new configuration from the repo

# Rebuild frontend
cd ..
docker-compose up -d --build frontend
```

### Option 3: Run Diagnostic Script
```bash
# On EC2 server
cd ytnotesmaker
chmod +x scripts/diagnose-ec2.sh
./scripts/diagnose-ec2.sh
```

**Note:** The diagnostic script uses `docker compose` syntax. If you encounter errors, edit the script and replace `docker compose` with `docker-compose`.

## Verification Steps

### 1. Check Container Status
```bash
docker-compose ps
```
Both containers should show "Up" status.

### 2. Check Nginx Configuration
```bash
docker-compose exec frontend nginx -t
```
Should show "syntax is ok" and "test is successful".

### 3. Test Health Endpoints
```bash
# Frontend health
curl http://localhost/health

# Backend health
curl http://localhost:5000/api/health
```

### 4. Test API Access
```bash
curl http://localhost/api/health
```
Should return: `{"status":"ok","service":"ytNotesMaker Backend"}`

### 5. Check Browser Access
Open your browser and navigate to:
```
http://ec2-13-49-158-58.eu-north-1.compute.amazonaws.com
```

## Troubleshooting

### If 403 Persists After Update

1. **Clear browser cache** - Hard refresh (Ctrl+F5 or Cmd+Shift+R)

2. **Check nginx error logs:**
   ```bash
   docker-compose logs frontend | grep -i error
   ```

3. **Verify file permissions:**
   ```bash
   docker-compose exec frontend ls -la /usr/share/nginx/html
   ```

4. **Test direct backend access:**
   ```bash
   curl http://localhost:5000/api/health
   ```

5. **Restart specific containers:**
   ```bash
   docker-compose restart frontend
   docker-compose restart backend
   ```

### Common Error Messages

#### "403 Forbidden" on static files
- **Cause:** File permissions in Docker container
- **Fix:** Rebuild frontend container: `docker-compose up -d --build frontend`

#### "403 Forbidden" on API calls
- **Cause:** Backend rejecting requests or nginx proxy issue
- **Fix:** Check backend logs: `docker-compose logs backend`

#### "502 Bad Gateway"
- **Cause:** Backend not responding
- **Fix:** Restart backend: `docker-compose restart backend`

#### "Connection refused"
- **Cause:** Containers not running or port conflicts
- **Fix:** Check container status: `docker-compose ps`

## Monitoring

### Real-time Log Monitoring
```bash
# All logs
docker-compose logs -f

# Specific container logs
docker-compose logs -f frontend
docker-compose logs -f backend
```

### Container Resource Usage
```bash
docker stats
```

## Performance Optimization

If you continue to experience issues after the fix:

1. **Increase timeouts further** in nginx.conf if processing long videos
2. **Add caching** for repeated requests
3. **Scale backend** if CPU/memory is constrained
4. **Use load balancer** for high traffic scenarios

## Additional Resources

- [Deployment Guide](DEPLOYMENT.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
- [Docker Compose Logs](https://docs.docker.com/compose/reference/logs/)
- [Nginx Debugging](https://nginx.org/en/docs/debugging_log.html)