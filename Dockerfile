# Rixly API Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers and system dependencies (for JavaScript rendering)
# This installs Chromium browser and all required system libraries
RUN playwright install chromium && \
    playwright install-deps chromium

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Make migration script executable
RUN chmod +x scripts/run_migrations.py

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Create entrypoint script that runs migrations then starts API
# Note: In development mode, file watching is enabled for hot reload
RUN echo '#!/bin/bash\n\
set -e\n\
echo "========================================="\n\
echo "Rixly API - Starting up..."\n\
echo "========================================="\n\
echo ""\n\
echo "Step 1: Running database migrations..."\n\
python scripts/run_migrations.py\n\
if [ $? -ne 0 ]; then\n\
    echo "ERROR: Migrations failed. Exiting."\n\
    exit 1\n\
fi\n\
echo ""\n\
echo "Step 2: Starting API server..."\n\
if [ "$ENVIRONMENT" != "production" ]; then\n\
    echo "  - Hot reload enabled (watching for file changes)"\n\
    echo "  - Edit files in ./core, ./modules, or ./api to see changes"\n\
fi\n\
echo "========================================="\n\
echo ""\n\
exec python run_api.py\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

# Run migrations and start API
CMD ["/entrypoint.sh"]

