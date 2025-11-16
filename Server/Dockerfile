# AlderSync Server Dockerfile
# This creates a containerized deployment of the AlderSync server for NAS deployment

# Use official Python runtime as base image
# Using 3.9 for better stability in Docker environments
FROM python:3.9-slim

# Set working directory in container
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

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
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the server using uvicorn
# host 0.0.0.0 allows external connections
# port 8000 is the standard AlderSync port
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
