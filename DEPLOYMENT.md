# AWS Deployment Guide: ytNotesMaker (Docker)

This guide walks you through Dockerizing and deploying **ytNotesMaker** to AWS using Docker Compose on an **AWS EC2 instance** (Recommended for local Ollama models) or **AWS ECS/App Runner** (for cloud LLMs).

---

## 🏗️ Architecture Overview

The app consists of 3 containerized services:
1. **Frontend**: React + Vite served via Nginx (Port 80)
2. **Backend**: Flask + LangGraph pipeline (Port 5000)
3. **Ollama**: Local AI inference engine for `llama3.2` & `nomic-embed-text` (Port 11434)

```
[ User Browser ] ───(HTTP 80)───> [ Frontend Container (Nginx) ]
                                          │
                                 (Proxy /api/* to :5000)
                                          ▼
                                  [ Backend Container ]
                                          │
                                 (OLLAMA_BASE_URL)
                                          ▼
                                   [ Ollama Container ]
```

---

## Option 1: AWS EC2 Deployment (Recommended)

Since Ollama requires ~4GB RAM and local inference, an EC2 instance (`t3.medium` or `t3.large`) is the easiest and most cost-effective option.

### Step 1: Launch an EC2 Instance
1. Open the [AWS EC2 Console](https://console.aws.amazon.com/ec2/).
2. Click **Launch Instance**.
3. **Name**: `ytnotesmaker-server`
4. **AMI**: Ubuntu 22.04 LTS or Amazon Linux 2023.
5. **Instance Type**: 
   - Recommended: `t3.medium` (2 vCPU, 4 GiB RAM) or `t3.large` (8 GiB RAM).
6. **Key Pair**: Select or create a `.pem` key pair.
7. **Network Settings / Security Group**:
   - Allow **SSH (Port 22)** from your IP.
   - Allow **HTTP (Port 80)** from Anywhere (`0.0.0.0/0`).
   - Allow **HTTPS (Port 443)** from Anywhere (`0.0.0.0/0`) (if adding SSL).
8. **Storage**: Set root volume size to at least **20 GB** (Ollama models require ~3-4 GB).

---

### Step 2: SSH into EC2 & Install Docker
Connect to your EC2 instance via SSH:
```bash
ssh -i /path/to/your-key.pem ubuntu@<YOUR_EC2_PUBLIC_IP>
```

Run the automated setup script or execute the following commands:
```bash
# Update packages
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git

# Enable and start Docker
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

# Log out and log back in to apply group changes
exit
```

---

### Step 3: Deploy Application
Re-connect via SSH:
```bash
ssh -i /path/to/your-key.pem ubuntu@<YOUR_EC2_PUBLIC_IP>
```

1. **Clone your repository** (or transfer files via SCP/Git):
```bash
git clone https://github.com/your-username/ytnotesmaker.git
cd ytnotesmaker
```

2. **Start the containers**:
```bash
docker compose up -d --build
```

3. **Verify running containers**:
```bash
docker compose ps
```

4. **Verify Ollama model pull**:
The `ollama-init` container will automatically pull `llama3.2` and `nomic-embed-text` into the persistent volume on first startup. You can check progress:
```bash
docker compose logs -f ollama-init
```

---

### Step 4: Access your Application
Open your browser and visit:
```
http://<YOUR_EC2_PUBLIC_IP>
```

---

## 🛠️ Management & Maintenance Commands

| Action | Command |
|---|---|
| View logs | `docker compose logs -f` |
| View backend logs | `docker compose logs -f backend` |
| Restart services | `docker compose restart` |
| Stop all services | `docker compose down` |
| Rebuild containers | `docker compose up -d --build` |

---

## 🔐 Optional: Enable HTTPS with Certbot (Let's Encrypt)

If you point a domain (e.g. `notes.yourdomain.com`) to your EC2 IP, you can secure it with SSL:

1. Install Certbot:
```bash
sudo apt-get install -y certbot python3-certbot-nginx
```

2. Generate Certificate:
```bash
sudo certbot --nginx -d notes.yourdomain.com
```
