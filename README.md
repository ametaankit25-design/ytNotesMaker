# 📺 YT Notes Maker

AI-powered YouTube video to structured study notes converter. Extracts transcripts and generates comprehensive PDFs.

## 🚀 Features

- **Transcript Extraction**: Multi-strategy fetching (InnerTube API, pytubefix, yt-dlp)
- **AI Notes Generation**: Structured notes using Groq/Gemini/OpenAI LLMs
- **PDF Export**: 3 formats (Summary, Cheatsheet, Flashcards)
- **React Frontend**: Modern UI with real-time progress
- **Flask Backend**: REST API with LangGraph pipeline

## 🛠️ Tech Stack

**Frontend:**
- React + Vite
- TailwindCSS
- Axios

**Backend:**
- Python Flask
- LangChain + LangGraph
- yt-dlp, pytubefix
- fpdf2 for PDF generation
- Groq/Gemini/OpenAI LLMs

## 📦 Deployment on Render

### Backend (Web Service)

1. **Create Web Service** on Render
2. **Connect GitHub** repo
3. **Configure:**
   - **Name**: `ytnotes-backend`
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r req.txt`
   - **Start Command**: `python flask_api.py`
   - **Environment Variables**:
     - `GROQ_API_KEY` = your_groq_api_key (get from console.groq.com)
     - `PORT` = 5000

### Frontend (Static Site)

1. **Create Static Site** on Render
2. **Connect GitHub** repo
3. **Configure:**
   - **Name**: `ytnotes-frontend`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `dist`

4. **Update API URL** in `frontend/src/App.jsx`:
   ```js
   const API_BASE_URL = "https://ytnotes-backend.onrender.com";
   ```

## 🔑 Environment Variables

Create `.env` file in backend:

```env
# LLM Configuration (choose one)
GROQ_API_KEY=gsk_your_api_key_here
# or
GEMINI_API_KEY=AIzaSy_your_key
# or
OPENAI_API_KEY=sk-your_key

# Optional: Local Ollama
OLLAMA_BASE_URL=http://localhost:11434
```

## 🧪 Local Development

### Backend

```bash
cd backend
pip install -r req.txt
python flask_api.py
# Runs on http://localhost:5000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:5173
```

## 📝 API Endpoints

- `POST /api/generate` - Generate notes from YouTube URL
- `GET /api/download/{job_id}/{pdf_type}` - Download PDF
- `GET /api/health` - Health check

## 🎯 Usage

1. Paste YouTube URL
2. Click "Generate Notes"
3. Download PDFs (Summary, Cheatsheet, Flashcards)

## 🔒 Cookies (Optional)

For better transcript extraction on restricted videos:

1. Export cookies from browser (using extension like "Get cookies.txt")
2. Save as `cookies.txt` in project root
3. Upload to Render as environment file

## 📄 License

MIT License

## 🤝 Contributing

Pull requests welcome!

## 🐛 Issues

Report issues on GitHub Issues page.

---

**Made with ❤️ by Ankit**
