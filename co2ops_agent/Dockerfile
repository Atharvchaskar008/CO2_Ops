# Dockerfile for CO2Ops AWS Sustainability ADK Backend
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    AWS_DEFAULT_REGION=us-east-1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source
COPY . /app

EXPOSE 8080

# Health check to ensure API server is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8080/ || exit 1

# Start ADK API server for AWS-optimized CO2Ops Agent
CMD ["adk", "api_server", "--host", "0.0.0.0", "--port", "8080", "--allow_origins", "*", "--auto_create_session", "/app"]
