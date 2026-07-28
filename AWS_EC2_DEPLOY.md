# 🚀 Deploy Backend on AWS EC2 with Docker

## Prerequisites
- AWS Account
- EC2 instance running (Ubuntu 22.04 recommended)
- SSH access to EC2
- Security group allowing port 5000

---

## 📋 Step-by-Step Deployment

### Step 1: Connect to EC2

```bash
ssh -i your-key.pem ubuntu@your-ec2-public-ip
```

---

### Step 2: Install Docker on EC2

```bash
# Update packages
sudo apt update

# Install Docker
sudo apt install -y docker.io

# Start Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group (no sudo needed)
sudo usermod -aG docker ubuntu

# Apply group changes (logout and login again, or run):
newgrp docker
```

---

### Step 3: Upload Backend Code to EC2

**Option A: Using Git (Recommended)**

```bash
# On EC2
git clone https://github.com/your-username/ytNotesMaker.git
cd ytNotesMaker/backend
```

**Option B: Using SCP from your local machine**

```bash
# On your local machine
scp -i your-key.pem -r backend ubuntu@your-ec2-public-ip:~/
```

---

### Step 4: Create .env File on EC2

```bash
# On EC2, in the backend directory
nano .env
```

Add:
```env
GROQ_API_KEY=your_groq_api_key_here
PORT=5000
```

Save: `Ctrl+O`, Enter, `Ctrl+X`

---

### Step 5: Build Docker Image

```bash
cd ~/backend  # or ~/ytNotesMaker/backend if using git

docker build -t ytnotesmaker-backend .
```

---

### Step 6: Run Docker Container

```bash
docker run -d \
  --name ytnotesmaker \
  -p 5000:5000 \
  --env-file .env \
  --restart unless-stopped \
  ytnotesmaker-backend
```

---

### Step 7: Verify It's Running

```bash
# Check container status
docker ps

# Check logs
docker logs ytnotesmaker

# Test health endpoint
curl http://localhost:5000/api/health
```

Expected: `{"status":"ok","service":"ytNotesMaker Backend"}`

---

### Step 8: Configure Security Group

In AWS Console:
1. Go to **EC2 → Security Groups**
2. Select your instance's security group
3. **Add Inbound Rule**:
   - Type: Custom TCP
   - Port: 5000
   - Source: 0.0.0.0/0 (or your IP)
4. **Save**

---

### Step 9: Test from Internet

```bash
curl http://your-ec2-public-ip:5000/api/health
```

---

## 🔧 Docker Management Commands

```bash
# Stop container
docker stop ytnotesmaker

# Start container
docker start ytnotesmaker

# Restart container
docker restart ytnotesmaker

# View logs
docker logs -f ytnotesmaker

# Update after code changes
docker stop ytnotesmaker
docker rm ytnotesmaker
docker build -t ytnotesmaker-backend .
docker run -d --name ytnotesmaker -p 5000:5000 --env-file .env --restart unless-stopped ytnotesmaker-backend
```

---

## 🌐 Update Frontend

Once backend is running, get your EC2 public IP and update frontend:

```bash
# frontend/.env.production
VITE_API_BASE_URL=http://your-ec2-public-ip:5000
```

Then redeploy frontend on Vercel/Netlify.

---

## 🔒 Optional: Setup HTTPS with Nginx

For production, use Nginx as reverse proxy with SSL:

```bash
# Install Nginx
sudo apt install -y nginx certbot python3-certbot-nginx

# Configure Nginx
sudo nano /etc/nginx/sites-available/ytnotesmaker
```

Add:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/ytnotesmaker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

---

## ✅ Summary

Your backend will be running at:
- **HTTP**: `http://your-ec2-public-ip:5000`
- **HTTPS** (if using Nginx): `https://your-domain.com`

Frontend can connect to this URL! 🚀
