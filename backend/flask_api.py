"""
flask_api.py
------------
Flask REST API backend for YT Notes Maker.
Wraps the LangGraph pipeline and serves PDF downloads.

Endpoints:
  POST /api/generate     — run the full pipeline
  GET  /api/download/<job_id>/<type>  — download a PDF
  GET  /api/health       — health check
"""

import os
import sys
import uuid

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

# Add the project root to path so we can import local modules
sys.path.insert(0, os.path.dirname(__file__))

from chains import notes_graph   # compiled LangGraph

app = Flask(__name__)
CORS(app)   # allow React dev server (port 5173) to talk to Flask (port 5000)

# In-memory store: job_id → {summary, cheatsheet, flashcards} pdf file paths
_pdf_store: dict[str, dict] = {}


# ──────────────────────────────────────────────
# POST /api/generate
# ──────────────────────────────────────────────
@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True, silent=True) or {}
    url          = (data.get("url")          or "").strip()
    instructions = (data.get("instructions") or "").strip()

    if not url:
        return jsonify({"error": "YouTube URL is required."}), 400

    initial_state = {
        "url":          url,
        "instructions": instructions,
        "transcript":   "",
        "notes":        None,
        "pdf_paths":    {},
        "error":        None,
    }

    result = notes_graph.invoke(initial_state)

    if result.get("error"):
        return jsonify({"error": result["error"]}), 500

    notes     = result["notes"]
    pdf_paths = result["pdf_paths"]

    # Store PDFs under a unique job id
    job_id = str(uuid.uuid4())
    _pdf_store[job_id] = pdf_paths

    return jsonify({
        "job_id": job_id,
        "notes": {
            "title":           notes.title,
            "summary":         notes.summary,
            "key_concepts":    notes.key_concepts,
            "bullet_points":   notes.bullet_points,
            "flashcards":      [
                {"question": f.question, "answer": f.answer}
                for f in notes.flashcards
            ],
            "important_quotes": notes.important_quotes or [],
        },
        "pdf_urls": {
            "summary":    f"/api/download/{job_id}/summary",
            "cheatsheet": f"/api/download/{job_id}/cheatsheet",
            "flashcards": f"/api/download/{job_id}/flashcards",
        },
    })


# ──────────────────────────────────────────────
# GET /api/download/<job_id>/<pdf_type>
# ──────────────────────────────────────────────
@app.route("/api/download/<job_id>/<pdf_type>")
def download(job_id: str, pdf_type: str):
    paths = _pdf_store.get(job_id)
    if not paths:
        return jsonify({"error": "Job not found."}), 404

    path = paths.get(pdf_type)
    if not path or not os.path.exists(path):
        return jsonify({"error": f"PDF type '{pdf_type}' not found."}), 404

    return send_file(
        path,
        as_attachment=True,
        download_name=f"yt_{pdf_type}.pdf",
        mimetype="application/pdf",
    )


# ──────────────────────────────────────────────
# GET /api/health
# ──────────────────────────────────────────────
@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "model": "llama3.2 (Ollama)"})


if __name__ == "__main__":
    print("Flask API running on http://localhost:5000")
    app.run(debug=False, port=5000, host="0.0.0.0")
