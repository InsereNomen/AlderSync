# AlderSync Server Dockerfile
# This creates a containerized deployment of the AlderSync server for NAS deployment

# Use official Python runtime as base image
# Using 3.9 for better stability in Docker environments
FROM python:3.9-slim

# Set working directory in container
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install system dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Note: Not upgrading pip to avoid potential Docker/WSL2 issues
RUN pip install --no-cache-dir -r requirements.txt

# Copy server application files
COPY *.py ./
COPY models/ ./models/
COPY managers/ ./managers/
COPY routes/ ./routes/
COPY templates/ ./templates/
COPY static/ ./static/

# Create necessary directories for data persistence
# These will be mounted as volumes in production
RUN mkdir -p /app/storage/Contemporary && \
    mkdir -p /app/storage/Traditional && \
    mkdir -p /app/database && \
    mkdir -p /app/client_downloads && \
    mkdir -p /app/logs

# Expose port 8000 for the FastAPI application
EXPOSE 8000

# Add health check to verify server is running
# Checks the /health endpoint every 30 seconds
# Uses curl with -k to accept self-signed certificates
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f -k https://localhost:8000/health || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the server using server.py
# This ensures SSL certificate setup code is executed
# The server.py script will check for SSL_DIR environment variable
# and configure HTTPS accordingly
CMD ["python", "server.py"]
