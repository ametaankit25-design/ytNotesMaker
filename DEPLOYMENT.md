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

# Run automated setup (Configures 4GB Swap + Installs Docker)
chmod +x scripts/setup-aws-ec2.sh
./scripts/setup-aws-ec2.sh

# Apply docker group permissions
sudo usermod -aG docker $USER
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

### Step 4: Start Docker Containers

Launch all services:
```bash
docker compose up -d --build
```

Check status:
```bash
docker compose ps
```

---

### Step 5: Access Your App

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
| Stop all containers | `docker compose down` |
