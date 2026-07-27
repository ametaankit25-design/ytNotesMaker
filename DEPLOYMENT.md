# AWS Free Tier (t3.micro) Deployment Guide: ytNotesMaker (Docker)

This guide is specifically optimized for running **ytNotesMaker** on an **AWS EC2 `t3.micro` instance** (Free Tier eligible: 1 vCPU, 1 GB RAM).

---

## 💡 How `t3.micro` Optimization Works

`t3.micro` instances have **1 GB of RAM**, which is normally tight for heavy AI workloads. We overcome this with two key strategies:

1. **4GB Swap Space**: The automated setup script configures a 4GB Swap file on your EBS disk to prevent Out-Of-Memory (OOM) crashes.
2. **Optional Free Cloud LLM (Groq / Gemini)**:
   - Setting `GROQ_API_KEY` (100% free) in `.env` makes note generation respond in **< 1 second** with 0 RAM usage on your EC2 instance!
   - If no API key is provided, it seamlessly falls back to self-hosted Ollama (`llama3.2`) using Swap space.

---

## 🏗️ Architecture

```
[ User Browser ] ───(HTTP 80)───> [ Frontend Container (Nginx) ]
                                          │
                                 (Proxy /api/* to :5000)
                                          ▼
                                  [ Backend Container ]
                                          │
                 ┌────────────────────────┴────────────────────────┐
                 ▼                                                 ▼
      (Cloud API: Groq / Gemini)                        (Local Ollama Container)
      Zero RAM / Instant Speed                          Fallback Self-Hosted LLM
```

---

## Step-by-Step AWS EC2 `t3.micro` Setup

### Step 1: Launch your `t3.micro` EC2 Instance
1. Open the [AWS EC2 Console](https://console.aws.amazon.com/ec2/).
2. Click **Launch Instance**.
3. **Name**: `ytnotesmaker-server`
4. **AMI**: Ubuntu 22.04 LTS (recommended).
5. **Instance Type**: Select **`t3.micro`** (Free Tier Eligible).
6. **Key Pair**: Select or create your `.pem` key pair.
7. **Network Settings / Security Group**:
   - Allow **SSH (Port 22)** from your IP.
   - Allow **HTTP (Port 80)** from Anywhere (`0.0.0.0/0`).
   - Allow **HTTPS (Port 443)** from Anywhere (`0.0.0.0/0`).
8. **Storage**: Set size to **20 GB** (gp3 volume).

---

### Step 2: SSH into EC2 & Run One-Line Setup
Connect via SSH:
```bash
ssh -i /path/to/your-key.pem ubuntu@<YOUR_EC2_PUBLIC_IP>
```

Clone the repository and run the setup script:
```bash
git clone https://github.com/ametaankit25-design/ytNotesMaker.git
cd ytnotesmaker

# Run automated setup (4GB Swap + Docker + cookies placeholder)
chmod +x scripts/setup-aws-ec2.sh scripts/deploy-ec2.sh
./scripts/setup-aws-ec2.sh

# Apply docker group permissions
newgrp docker
```

---

### Step 3: Configure Environment (Optional for Maximum Speed)

Create a `.env` file inside `ytnotesmaker`:
```bash
nano .env
```

*(Optional for superfast responses on t3.micro)*:
```env
# Optional: Add Groq API Key (Free tier at https://console.groq.com)
GROQ_API_KEY=gsk_your_groq_api_key_here
```
*If you leave `.env` empty, the app will use local Ollama (`llama3.2`).*

---

### Step 4: YouTube cookies (required on EC2)

EC2 uses a **datacenter IP**. YouTube often blocks transcript APIs without browser cookies.

**On your laptop (Chrome/Firefox):**

1. Install extension **"Get cookies.txt LOCALLY"** (Chrome Web Store)
2. Open a **private/incognito** window → go to [youtube.com](https://youtube.com) and sign in
3. Export cookies → save as `cookies.txt` (Netscape format)

**Upload to EC2:**

```bash
# From your laptop (replace paths/IPs):
scp -i /path/to/your-key.pem cookies.txt ubuntu@<YOUR_EC2_PUBLIC_IP>:~/ytnotesmaker/cookies.txt
```

**Or create empty file first, then paste on EC2:**

```bash
touch cookies.txt
nano cookies.txt   # paste exported cookie file contents
```

Without valid cookies, the app tries fallback strategies (`pytubefix`, `captionTracks`, yt-dlp `tv_embedded`), but results are not guaranteed on EC2.

---

### Step 5: Start Docker Containers

```bash
chmod +x scripts/deploy-ec2.sh
./scripts/deploy-ec2.sh
```

Or manually:

```bash
touch cookies.txt
mkdir -p oauth_cache
docker compose up -d --build
```

**Test transcript extraction on EC2:**

```bash
docker compose exec backend python test_transcript.py \
  "https://www.youtube.com/watch?v=rfscVS0vtbw"
```

Expected: `SUCCESS` with 200K+ characters and `VIDEO TITLE:` in output.

Check backend logs for strategy used:

```bash
docker compose logs backend | grep Transcript
```

---

### Step 6: Access Your App

Open your web browser and visit:
```
http://<YOUR_EC2_PUBLIC_IP>
```

---

## 🛠️ Handy Commands

| Action | Command |
|---|---|
| View live logs | `docker compose logs -f` |
| Check memory & swap usage | `free -h` |
| Restart all containers | `docker compose restart` |
| Test YouTube transcript on EC2 | `docker compose exec backend python test_transcript.py` |
| Re-deploy after git pull | `./scripts/deploy-ec2.sh` |
| Stop all containers | `docker compose down` |

---

## YouTube on EC2 — Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Live transcript unavailable (YouTube bot-detection)` | Upload valid `cookies.txt` and restart: `docker compose restart backend` |
| `Strategy 4 (yt-dlp) ... Sign in to confirm you're not a bot` | Same — export fresh cookies from incognito browser session |
| Empty PDF / generic notes | Check transcript test above; add `GROQ_API_KEY` to `.env` |
| Container won't start | Ensure `touch cookies.txt` exists before `docker compose up` |

Transcript fetch order in `backend/chains.py`:

1. **pytubefix** (ANDROID_VR / TV clients)
2. **captionTracks** scrape (no PO token)
3. **youtube-transcript-api**
4. **yt-dlp** with PO-token-free clients + cookies
