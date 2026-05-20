# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Install system dependencies for curl-cffi / compiling
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libcurl4-openssl-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency list first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY api/ ./api/
COPY run.py .
COPY tests/Gemini-API-master/src/ ./tests/Gemini-API-master/src/

# Create directories for cookie cache and generated images
RUN mkdir -p /tmp/gemini_webapi /app/generated_images

EXPOSE 8000

# Default: run with uvicorn (production)
CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8000"]
