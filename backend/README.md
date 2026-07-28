# YT Notes Maker - Backend

Flask REST API backend for YT Notes Maker. Extracts YouTube transcripts and generates AI-powered study notes.

## 🚀 Quick Deploy on AWS EC2

### Prerequisites
- AWS EC2 instance (Ubuntu 22.04)
- Docker installed
- Port 5000 open in security group

### Deploy in 3 Commands

```bash
# 1. Upload code to EC2 or clone from git
git clone your-repo
cd ytNotesMaker/backend

# 2. Create .env file
echo "GROQ_API_KEY=your_groq_api_key_here" > .env
echo "PORT=5000" >> .env

# 3. Run deployment script
chmod +x deploy-ec2.sh
./deploy-ec2.sh
```

**Done!** Backend runs at `http://your-ec2-ip:5000`

---

## 🐳 Docker Commands

```bash
# Build
docker build -t ytnotesmaker-backend .

# Run
docker run -d --name ytnotesmaker -p 5000:5000 --env-file .env ytnotesmaker-backend

# Logs
docker logs -f ytnotesmaker

# Stop
docker stop ytnotesmaker

# Restart
docker restart ytnotesmaker
```

---

## 🧪 Test

```bash
# Health check
curl http://localhost:5000/api/health

# Generate notes
curl -X POST http://localhost:5000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

---

## 📁 Project Structure

```
backend/
├── flask_api.py          # Flask REST API
├── chains.py             # LangGraph pipeline
├── llm.py               # LLM configuration
├── notes_schema.py      # Pydantic schemas
├── pdf_generator.py     # PDF generation
├── visual_context.py    # Video frame extraction
├── req.txt              # Python dependencies
├── Dockerfile           # Docker configuration
└── deploy-ec2.sh        # Deployment script
```

---

## 🔑 Environment Variables

```env
GROQ_API_KEY=your_groq_api_key
PORT=5000
```

---

## 📚 API Endpoints

### Health Check
```
GET /api/health
```

### Generate Notes
```
POST /api/generate
Body: {
  "url": "youtube_url",
  "instructions": "optional_custom_instructions"
}
```

### Download PDF
```
GET /api/download/{job_id}/{pdf_type}
```

---

## 🛠️ Tech Stack

- Flask + Flask-CORS
- LangChain + LangGraph
- Groq LLM (llama-3.3-70b)
- yt-dlp + youtube-transcript-api
- fpdf2

---

## 📖 Full Documentation

See `AWS_EC2_DEPLOY.md` for detailed deployment guide.
