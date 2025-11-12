FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including ODBC for SQL Server
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    unixodbc \
    unixodbc-dev \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Microsoft ODBC Driver for SQL Server
RUN curl https://packages.microsoft.com/keys/microsoft.asc > /etc/apt/trusted.gpg.d/microsoft.asc \
    && echo "deb [arch=amd64] https://packages.microsoft.com/debian/11/prod bullseye main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and SSL certificates
COPY . .

# Ensure ca.pem is properly copied and has correct permissions
RUN if [ -f "ca.pem" ]; then \
        echo "✅ ca.pem found, copying to /app/ca.pem"; \
        cp ca.pem /app/ca.pem && \
        chmod 644 /app/ca.pem; \
    else \
        echo "❌ ca.pem not found in project root!"; \
    fi

# Create a non-root user to run the application
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

ENV PORT=10000
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/api/health || exit 1

CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 120 app:app
