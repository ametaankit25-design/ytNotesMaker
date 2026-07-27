# ─────────────────────────────────────────────────────────────────
# Backend — Flask API + LangGraph + FPDF
# Pure Python 3.11 Slim (No apt-get dependencies needed)
# ─────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install dependencies directly using pre-compiled wheels
COPY req.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r req.txt

# Copy backend source code
COPY . .

# Create output directory for generated PDFs
RUN mkdir -p /app/output

EXPOSE 5000

CMD ["python", "flask_api.py"]
