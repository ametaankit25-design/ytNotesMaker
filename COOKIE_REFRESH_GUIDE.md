# Cookie Refresh Guide for YouTube Transcript Extraction

## Problem: Cookies Expired

YouTube cookies expire over time, causing transcript extraction failures. When cookies expire, you'll see errors like:
- "Sign in to confirm you're not a bot"
- HTTP 403 Forbidden errors
- Empty transcript results
- "Live transcript unavailable (YouTube bot-detection)"

## Solution 1: Quick Cookie Refresh (Recommended)

### Step 1: Export Fresh Cookies from Browser

**Chrome/Edge:**
1. Install the "Get cookies.txt LOCALLY" extension from Chrome Web Store
2. Open an **incognito/private window** in your browser
3. Go to [youtube.com](https://youtube.com) and sign in to your Google account
4. Click the extension icon and export cookies as `cookies.txt` (Netscape format)
5. Save the file to your computer

**Firefox:**
1. Install the "cookies.txt" extension from Firefox Add-ons
2. Open a **private window** in Firefox
3. Go to [youtube.com](https://youtube.com) and sign in
4. Click the extension and export cookies as `cookies.txt`
5. Save the file to your computer

### Step 2: Upload to EC2 Server

```bash
# From your local computer (replace paths)
scp -i "dev-ankit-key.pem" cookies.txt ec2-user@ec2-13-49-158-58.eu-north-1.compute.amazonaws.com:~/ytnotesmaker/cookies.txt
```

### Step 3: Restart Backend Container

```bash
# Connect to EC2
ssh -i "dev-ankit-key.pem" ec2-user@ec2-13-49-158-58.eu-north-1.compute.amazonaws.com

# Navigate to project
cd ytnotesmaker

# Restart backend to load new cookies
docker-compose restart backend

# Check logs to verify cookies are loaded
docker-compose logs backend | grep -i cookie
```

## Solution 2: Test Cookies First

Before uploading, you can test if your cookies are valid:

```bash
# On your local machine (in the project directory)
cd backend
python test_cookies.py
```

This will show:
- ✓ Cookies file exists
- ✓ Cookies can be read  
- ✓ YouTube accessible
- ✓ Signed in to YouTube

If the test shows cookies are expired, export fresh ones.

## Solution 3: Automatic Cookie Validation

The updated backend now includes automatic cookie validation:

- **Validation Interval**: Every 30 minutes
- **Validation Method**: Tests YouTube access with current cookies
- **Fallback**: If cookies expire, automatically switches to no-cookies strategies
- **Cache**: Validation results cached for 5 minutes

### Configure Validation Settings

Edit `backend/chains.py` to adjust:

```python
# In CookieManager class __init__:
self.cookie_refresh_interval = 1800  # Seconds (30 minutes)
```

## Solution 4: Use Without Cookies (Fallback)

If cookies continue to cause issues, the application can work without them:

```bash
# Remove or rename cookies file
mv cookies.txt cookies.txt.backup

# Restart backend
docker-compose restart backend
```

**Note:** Without cookies, transcript extraction may be less reliable on EC2 due to YouTube's datacenter IP blocking.

## Solution 5: Multiple Cookie Files (Advanced)

For high-traffic scenarios, maintain multiple cookie files:

```bash
# Create multiple cookie files
cookies_account1.txt
cookies_account2.txt
cookies_account3.txt

# Rotate them periodically
# This requires code modifications to cycle through different files
```

## Monitoring Cookie Health

### Check Backend Logs for Cookie Issues:

```bash
# Connect to EC2
ssh -i "dev-ankit-key.pem" ec2-user@ec2-13-49-158-58.eu-north-1.compute.amazonaws.com

# Check cookie-related logs
docker-compose logs backend | grep -i cookie
```

Look for:
- `[CookieManager] Refreshed and validated cookies` - Good
- `[CookieManager] Cookies expired or invalid` - Need refresh
- `[Transcript] Strategy 4 failed: cookies` - Expired cookies

### Manual Cookie Testing on EC2:

```bash
# On EC2 server
cd ytnotesmaker/backend
docker-compose exec backend python test_cookies.py
```

## Best Practices

### 1. Regular Cookie Refresh
- **Frequency**: Every 1-2 weeks
- **Method**: Export fresh cookies from incognito browser session
- **Testing**: Use `test_cookies.py` before uploading

### 2. Use Incognito/Private Windows
- Always export cookies from incognito sessions
- This ensures clean, uncorrupted cookies
- Avoids conflicts with browser extensions

### 3. Monitor for Failures
- Check logs regularly for cookie-related errors
- Set up alerts for repeated authentication failures
- Test with known-good videos after cookie refresh

### 4. Backup Working Cookies
```bash
# When cookies are working, backup them
cp cookies.txt cookies.txt.working_backup

# If new cookies fail, restore backup
cp cookies.txt.working_backup cookies.txt
docker-compose restart backend
```

## Troubleshooting

### Issue: Cookies Not Loading

**Symptoms:**
- Logs show "Could not load cookies"
- Application acts as if no cookies exist

**Solutions:**
1. Check file permissions: `ls -la cookies.txt`
2. Ensure file is readable: `chmod 644 cookies.txt`
3. Verify file format (should be Netscape format)
4. Test with `python test_cookies.py`

### Issue: Cookies Work Initially Then Fail

**Symptoms:**
- Works for first few requests
- Then starts failing with authentication errors

**Solutions:**
1. YouTube may have rate-limited your account
2. Wait 30 minutes before trying again
3. Use a different Google account for cookies
4. Reduce request frequency (rate limiting)

### Issue: Incognito Cookies Don't Work

**Symptoms:**
- Fresh cookies from incognito still fail
- Test script shows "Not signed in"

**Solutions:**
1. Ensure you're fully signed in to YouTube in incognito
2. Try a different browser
3. Check if 2FA is interfering
4. Export cookies after watching a video (ensures session is active)

### Issue: All Strategies Fail Without Cookies

**Symptoms:**
- With cookies: authentication errors
- Without cookies: bot detection

**Solutions:**
1. Try a different EC2 instance/region
2. Use a proxy service
3. Implement request queuing with longer delays
4. Consider using cloud LLM APIs (Groq/Gemini) for better reliability

## Automated Cookie Refresh Script

Create a script to automate cookie refresh:

```bash
#!/bin/bash
# scripts/auto-refresh-cookies.sh

echo "Checking cookie health..."
cd /path/to/ytnotesmaker/backend

# Test current cookies
python test_cookies.py
RESULT=$?

if [ $RESULT -ne 0 ]; then
    echo "Cookies failed validation"
    echo "Please export fresh cookies and upload to:"
    echo "  ~/ytnotesmaker/cookies.txt"
    echo "Then run: docker-compose restart backend"
else
    echo "Cookies are healthy"
fi
```

Set up as a cron job:
```bash
# Run daily at 3 AM
0 3 * * * /path/to/scripts/auto-refresh-coins.sh >> /var/log/cookie-check.log 2>&1
```

## Alternative: No-Cookie Mode Configuration

If you prefer to run without cookies entirely:

```bash
# Remove cookies file
rm cookies.txt

# Create empty placeholder
touch cookies.txt

# Update docker-compose.yml to comment out cookies mount
# volumes:
#   - ./cookies.txt:/app/cookies.txt  # Comment this out

# Restart
docker-compose down
docker-compose up -d --build
```

**Note:** This will reduce transcript extraction success rate on EC2.

## Summary

**For immediate fix:**
1. Export fresh cookies from incognito browser window
2. Upload to EC2: `scp cookies.txt ec2-user@ec2-ip:~/ytnotesmaker/`
3. Restart backend: `docker-compose restart backend`

**For long-term stability:**
1. Use the automatic cookie validation system
2. Test cookies regularly with `test_cookies.py`
3. Refresh cookies every 1-2 weeks
4. Monitor logs for cookie-related errors

The enhanced cookie management system will automatically detect expired cookies and switch to fallback strategies, but fresh cookies will always provide the best results.