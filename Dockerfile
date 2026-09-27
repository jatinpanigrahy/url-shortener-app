# Base image: Python 3.12 slim for minimal container footprint (~150MB)
FROM python:3.12-slim

# Application working directory inside the container
WORKDIR /app

# Copy dependency manifest first to utilize Docker build layer caching
COPY requirements.txt .

# Install production dependencies without local wheel caching
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and configuration files
COPY . .

# Expose standard HTTP port
EXPOSE 5000

# Run Gunicorn: 1 worker with 4 threads maintains shared memory for the in-memory rate limiter
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "src.app:app"]