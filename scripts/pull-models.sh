#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# scripts/pull-models.sh
# Run this AFTER `docker compose up -d ollama` to pull LLM models.
# Only needs to run once — models are stored in the ollama_data volume.
# ─────────────────────────────────────────────────────────────────
set -e

echo "================================================"
echo "  ytNotesMaker — Pulling Ollama Models"
echo "================================================"

# Wait for Ollama to be ready
echo "Waiting for Ollama service..."
until docker compose exec ollama curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
  printf '.'
  sleep 3
done
echo ""
echo "Ollama is ready!"

echo ""
echo "Pulling llama3.2 (~2 GB)..."
docker compose exec ollama ollama pull llama3.2

echo ""
echo "Pulling nomic-embed-text (~274 MB)..."
docker compose exec ollama ollama pull nomic-embed-text

echo ""
echo "================================================"
echo "  All models pulled successfully!"
echo "  llama3.2        — LLM for notes generation"
echo "  nomic-embed-text — Embeddings"
echo "================================================"
