# Amazon KPI Automation - Cloud Run Container
# Base image: Playwright Python with Chromium

FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PORT=8080

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Install Playwright browsers
RUN playwright install chromium && \
    playwright install-deps chromium

# Copy application code
COPY src/ ./src/

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE ${PORT}

# Run with Gunicorn
CMD exec gunicorn \
    --bind :${PORT} \
    --workers 1 \
    --threads 2 \
    --timeout 900 \
    --keep-alive 5 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    "amazon_kpi.main:create_app()"
