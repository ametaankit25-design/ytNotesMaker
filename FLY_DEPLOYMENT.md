# 🚀 Fly.io Deployment Guide

Complete step-by-step guide to deploy YT Notes Maker backend on Fly.io.

## Prerequisites

- Fly.io account (free)
- Git installed
- Groq API key (get from console.groq.com)

---

## Step 1: Install Fly CLI

### Windows (PowerShell):
```powershell
iwr https://fly.io/install.ps1 -useb | iex
```

### Linux/Mac:
```bash
curl -L https://fly.io/install.sh | sh
```

### Verify installation:
```bash
flyctl version
```

---

## Step 2: Login to Fly.io

```bash
flyctl auth login
```

Browser खुलेगा - login karo.

---

## Step 3: Deploy Backend

```bash
cd backend

# Initialize Fly app (using existing fly.toml)
flyctl launch --copy-config --no-deploy

# Set secrets
flyctl secrets set GROQ_API_KEY=gsk_your_api_key_here

# Deploy!
flyctl deploy
```

---

## Step 4: Verify Deployment

```bash
# Check status
flyctl status

# View logs
flyctl logs

# Open in browser
flyctl open
```

Backend URL will be: `https://ytnotesmaker-backend.fly.dev`

---

## Step 5: Test API

```bash
# Health check
curl https://ytnotesmaker-backend.fly.dev/api/health

# Should return:
# {"status":"ok","service":"ytNotesMaker Backend"}
```

---

## Step 6: Upload Cookies (Optional but Recommended)

For better YouTube transcript extraction:

```bash
# Upload cookies.txt as secret
flyctl secrets set COOKIES_CONTENT="$(cat ../cookies.txt)"
```

Then update `chains.py` to use this secret if `cookies.txt` doesn't exist.

---

## Configuration

### fly.toml Settings:

```toml
app = "ytnotesmaker-backend"
primary_region = "sin"  # Singapore

[env]
  PORT = "8080"

[http_service]
  internal_port = 8080
  force_https = true
```

### Change Region:

```bash
# Available regions:
flyctl platform regions

# Update fly.toml primary_region to your choice:
# sin = Singapore (Asia)
# lax = Los Angeles (US West)
# fra = Frankfurt (Europe)
# syd = Sydney (Australia)
```

---

## Monitoring

### View Logs:
```bash
flyctl logs -a ytnotesmaker-backend
```

### SSH into container:
```bash
flyctl ssh console -a ytnotesmaker-backend
```

### Scale (if needed):
```bash
# Scale to 2 instances
flyctl scale count 2

# Scale memory
flyctl scale memory 512
```

---

## Costs

**Free Tier Includes:**
- 3 shared-cpu VMs
- 256MB RAM per VM
- 3GB persistent volume storage
- 160GB outbound data transfer

**Your app will use:**
- 1 VM (within free tier) ✅
- Auto-stop when idle (saves resources) ✅

---

## Troubleshooting

### Build Failed:

```bash
# Clean rebuild
flyctl deploy --no-cache
```

### App Crashed:

```bash
# Check logs
flyctl logs

# Restart
flyctl apps restart ytnotesmaker-backend
```

### Port Issues:

Make sure `flask_api.py` uses `PORT` env variable:
```python
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
```

### YouTube Bot Detection:

1. Upload fresh cookies
2. Use InnerTube API strategy (already in code)
3. Fly.io has better IP reputation than Render

---

## Update Backend

```bash
cd backend

# Pull latest code
git pull origin main

# Redeploy
flyctl deploy
```

---

## Update Frontend URL

After backend deploys, update frontend `App.jsx`:

```javascript
const API_BASE_URL = import.meta.env.PROD 
  ? 'https://ytnotesmaker-backend.fly.dev'  // Your Fly.io URL
  : 'http://localhost:5000'
```

Then redeploy frontend on Render.

---

## Useful Commands

```bash
# App info
flyctl info

# List all apps
flyctl apps list

# Delete app (if needed)
flyctl apps destroy ytnotesmaker-backend

# View metrics
flyctl metrics

# View secrets
flyctl secrets list
```

---

## Support

- Fly.io Docs: https://fly.io/docs/
- Community Forum: https://community.fly.io/
- Status: https://status.fly.io/

---

**Deployment Time:** ~5 minutes  
**Zero Downtime:** Yes  
**Auto SSL:** Yes  
**Custom Domain:** Free (via CNAME)

Happy deploying! 🚀
