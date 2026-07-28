# 🚀 Vercel Deployment Guide

Deploy YT Notes Maker backend on Vercel (Serverless).

## ⚠️ Important Notes

**Vercel Limitations:**
- **10s execution timeout** on Hobby plan (60s on Pro)
- **50MB deployment size** limit
- **Serverless functions** (cold starts possible)

**Best for:** Quick deploys, moderate traffic  
**Not ideal for:** Long-running transcript extraction (might timeout)

---

## Prerequisites

- Vercel account (free)
- Vercel CLI installed
- Groq API key

---

## Step 1: Install Vercel CLI

```bash
npm install -g vercel
```

---

## Step 2: Login

```bash
vercel login
```

---

## Step 3: Deploy

```bash
# From project root
vercel

# Follow prompts:
# - Setup and deploy? Yes
# - Which scope? (your account)
# - Link to existing project? No
# - Project name? ytnotesmaker-backend
# - Directory? ./ (root)
# - Override settings? No
```

---

## Step 4: Add Environment Variable

### Via Dashboard:
1. Go to: https://vercel.com/dashboard
2. Select project: **ytnotesmaker-backend**
3. Settings → Environment Variables
4. Add:
   ```
   Key: GROQ_API_KEY
   Value: <your_groq_api_key_here>
   ```
5. Click **Save**

### Via CLI:
```bash
vercel env add GROQ_API_KEY
# Paste your API key when prompted
```

---

## Step 5: Redeploy with Env Vars

```bash
vercel --prod
```

---

## Step 6: Get URL

After deployment, you'll get URL like:
```
https://ytnotesmaker-backend.vercel.app
```

Test it:
```bash
curl https://ytnotesmaker-backend.vercel.app/api/health
```

---

## Update Frontend

Update `frontend/src/App.jsx`:

```javascript
const API_BASE_URL = import.meta.env.PROD 
  ? 'https://ytnotesmaker-backend.vercel.app'  // Your Vercel URL
  : 'http://localhost:5000'
```

---

## Project Structure for Vercel

```
ytNotesMaker/
├── backend/
│   ├── flask_api.py      # Main Flask app
│   ├── wsgi.py           # WSGI wrapper for Vercel
│   ├── chains.py
│   ├── llm.py
│   ├── req.txt
│   └── ...
├── vercel.json           # Vercel configuration
└── README.md
```

---

## Deployment Commands

```bash
# Development deploy (preview URL)
vercel

# Production deploy
vercel --prod

# View logs
vercel logs

# List deployments
vercel ls

# Remove deployment
vercel rm ytnotesmaker-backend
```

---

## Troubleshooting

### Timeout Errors

**Problem:** Function timeout after 10s

**Solutions:**
1. Upgrade to Vercel Pro (60s timeout)
2. Optimize transcript fetching
3. Use faster LLM (Groq is fast)
4. Consider alternative platform (Fly.io, Railway)

---

### Cold Starts

**Problem:** First request slow

**Solutions:**
1. Keep backend warm with cron job
2. Accept cold starts (5-10s delay)
3. Show loading indicator on frontend

---

### Deployment Size

**Problem:** Exceeds 50MB limit

**Solution:**
```bash
# Check size
du -sh backend/

# Remove unnecessary packages from req.txt
# Use lighter alternatives
```

---

### CORS Issues

Flask-CORS already configured in `flask_api.py`:
```python
from flask_cors import CORS
CORS(app)
```

---

## Monitoring

### View Logs:
```bash
vercel logs ytnotesmaker-backend --follow
```

### Analytics:
- Dashboard → Analytics
- See requests, errors, performance

---

## Cost

**Hobby Plan (Free):**
- 100GB bandwidth/month
- 100 hours serverless function execution
- 6000 build minutes

**Your usage (estimated):**
- ~1-2s per request
- Should fit in free tier easily ✅

---

## Alternative: Deploy Frontend on Vercel Too

```bash
cd frontend

# Deploy frontend
vercel

# Production
vercel --prod
```

Then you have:
- Backend: `https://ytnotesmaker-backend.vercel.app`
- Frontend: `https://ytnotesmaker.vercel.app`

---

## Custom Domain (Optional)

1. Vercel Dashboard → Domains
2. Add domain: `api.yourdomain.com`
3. Update DNS (CNAME record)
4. Done! Auto SSL ✅

---

## Useful Links

- Vercel Dashboard: https://vercel.com/dashboard
- Vercel Docs: https://vercel.com/docs
- Vercel CLI: https://vercel.com/docs/cli

---

**Deployment Time:** ~2 minutes  
**Auto Deploy:** Yes (from GitHub)  
**Free SSL:** Yes  
**Global CDN:** Yes  

Deploy now! 🚀
