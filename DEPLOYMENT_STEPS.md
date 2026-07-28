# 🚀 Complete Deployment Steps

## Option 1: Vercel (Recommended - Fastest)

### Step 1: Deploy Backend

```bash
# Deploy backend to Vercel
vercel

# Add Groq API key
vercel env add GROQ_API_KEY
# Paste your API key when prompted

# Production deploy
vercel --prod
```

**Note your backend URL:** `https://ytnotesmaker-backend-xxxx.vercel.app`

---

### Step 2: Update Frontend Environment

Edit `frontend/.env.production`:
```env
VITE_API_BASE_URL=https://ytnotesmaker-backend-xxxx.vercel.app
```
*(Replace with YOUR actual Vercel backend URL)*

---

### Step 3: Deploy Frontend

```bash
cd frontend

# Deploy to Vercel
vercel --prod
```

**Done!** Your app is live! 🎉

---

## Option 2: Render (Free Tier)

### Step 1: Deploy Backend on Render

1. Go to https://dashboard.render.com
2. **New → Web Service**
3. Connect GitHub: `ytNotesMaker` repo
4. **Configure:**
   ```
   Name: ytnotesmaker-backend
   Root Directory: backend
   Build Command: pip install -r req.txt
   Start Command: python flask_api.py
   ```
5. **Environment Variables:**
   ```
   GROQ_API_KEY = <your_groq_api_key_here>
   PORT = 5000
   ```
6. **Create Web Service**

**Backend URL:** `https://ytnotesmaker-backend.onrender.com`

---

### Step 2: Update Frontend Environment

Edit `frontend/.env.production`:
```env
VITE_API_BASE_URL=https://ytnotesmaker-backend.onrender.com
```

---

### Step 3: Deploy Frontend on Render

1. **New → Static Site**
2. Connect GitHub: `ytNotesMaker` repo
3. **Configure:**
   ```
   Name: ytnotesmaker-frontend
   Root Directory: frontend
   Build Command: npm install && npm run build
   Publish Directory: dist
   ```
4. **Environment Variables:**
   ```
   VITE_API_BASE_URL = https://ytnotesmaker-backend.onrender.com
   ```
5. **Create Static Site**

**Frontend URL:** `https://ytnotesmaker-frontend.onrender.com`

---

## Testing Your Deployment

### 1. Test Backend Health

```bash
curl https://your-backend-url.vercel.app/api/health
```

Expected: `{"status":"ok","service":"ytNotesMaker Backend"}`

### 2. Test Frontend

1. Open: `https://your-frontend-url.vercel.app`
2. Paste YouTube link: `https://www.youtube.com/watch?v=rfscVS0vtbw`
3. Click **Generate Notes**
4. Check browser console for API calls

### 3. Check Browser Console

Open DevTools (F12) → Console tab:

Should see:
```
[Frontend] Using API: https://your-backend-url.vercel.app
```

Should NOT see CORS errors.

---

## Troubleshooting

### ❌ Error: "Failed to fetch" or "Network Error"

**Cause:** Frontend can't reach backend

**Fix:**
1. Check `frontend/.env.production` has correct backend URL
2. Rebuild frontend: `cd frontend && npm run build`
3. Redeploy frontend

---

### ❌ Error: "CORS policy blocked"

**Cause:** Backend CORS not configured

**Fix:** Already configured in `flask_api.py`:
```python
from flask_cors import CORS
CORS(app)
```

If still issues, check backend logs.

---

### ❌ Backend shows "Application failed to respond"

**Cause:** 
- Missing environment variable
- Deployment error

**Fix:**
1. Check backend logs (Vercel/Render dashboard)
2. Verify `GROQ_API_KEY` is set
3. Check for errors in logs

---

### ❌ "YouTube bot detection" errors in logs

**Cause:** Datacenter IP blocked by YouTube

**Solutions:**
1. Upload `cookies.txt` (see VERCEL_DEPLOYMENT.md)
2. Use better datacenter (Vercel/Fly.io better than Render)
3. InnerTube API strategy already in code (should work)

---

## Environment Variables Summary

### Backend (.env or platform env vars):
```env
GROQ_API_KEY=<your_groq_api_key_here>
PORT=5000
```

### Frontend (.env.production):
```env
VITE_API_BASE_URL=https://your-backend-url.vercel.app
```

---

## Post-Deployment Checklist

- [ ] Backend health check passes
- [ ] Frontend loads without errors
- [ ] Can paste YouTube URL
- [ ] Generate button works
- [ ] Transcript fetches successfully
- [ ] Notes generate correctly
- [ ] PDFs download work
- [ ] No CORS errors in console
- [ ] Cookies uploaded (if needed)

---

## Quick Commands

```bash
# Redeploy backend (Vercel)
vercel --prod

# Redeploy frontend (Vercel)
cd frontend && vercel --prod

# View backend logs (Vercel)
vercel logs

# Check environment variables (Vercel)
vercel env ls
```

---

**Need help?** Check platform-specific docs:
- Vercel: `VERCEL_DEPLOYMENT.md`
- General: `README.md`

Happy deploying! 🚀
