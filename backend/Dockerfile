# ─────────────────────────────────────────────────────────────────
# Backend — Flask API + LangGraph + FPDF
# ─────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

COPY req.txt .
RUN pip install --no-cache-dir -r req.txt

COPY . .

RUN mkdir -p /app/output

EXPOSE 5000

CMD ["python", "flask_api.py"]
