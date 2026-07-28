FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY req.txt .
RUN pip install --no-cache-dir -r req.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8080

# Set environment
ENV PORT=8080

# Run app
CMD ["python", "flask_api.py"]
