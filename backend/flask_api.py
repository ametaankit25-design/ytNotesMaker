"""
flask_api.py
------------
Flask REST API backend for YT Notes Maker.
Wraps the LangGraph pipeline and serves PDF downloads.
"""

import os
import sys
import uuid
import traceback

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(__file__))

from chains import notes_graph

app = Flask(__name__)
CORS(app)

_pdf_store: dict[str, dict] = {}


@app.errorhandler(Exception)
def handle_global_exception(e):
    """Ensure all backend errors return clean JSON, never raw HTML tracebacks."""
    print(f"[Global Exception Handler] {e}")
    traceback.print_exc()
    return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


@app.route("/api/generate", methods=["POST"])
def generate():
    try:
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

        print(f"[API Generate] Invoking notes graph for URL: {url}")
        result = notes_graph.invoke(initial_state)

        if result.get("error"):
            print(f"[API Generate Error] {result['error']}")
            return jsonify({"error": result["error"]}), 500

        notes     = result.get("notes")
        pdf_paths = result.get("pdf_paths", {})

        if not notes:
            return jsonify({"error": "Failed to generate structured notes."}), 500

        job_id = str(uuid.uuid4())
        _pdf_store[job_id] = pdf_paths

        return jsonify({
            "job_id": job_id,
            "notes": {
                "title":            notes.title,
                "summary":          notes.summary,
                "key_concepts":     notes.key_concepts,
                "bullet_points":    notes.bullet_points,
                "flashcards":       [
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
    except Exception as e:
        print(f"[API Generate Exception] {e}")
        traceback.print_exc()
        return jsonify({"error": f"Server processing error: {str(e)}"}), 500


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


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "ytNotesMaker Backend"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Flask API running on http://0.0.0.0:{port}")
    app.run(debug=False, port=port, host="0.0.0.0")
