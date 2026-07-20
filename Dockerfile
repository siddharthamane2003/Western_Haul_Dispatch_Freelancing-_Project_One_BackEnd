# ─────────────────────────────────────────────
# Builder Stage
# ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ─────────────────────────────────────────────
# Production Stage
# ─────────────────────────────────────────────
FROM python:3.12-slim AS production

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*


# Copy installed Python packages
COPY --from=builder /usr/local/lib/python3.12 \
    /usr/local/lib/python3.12

COPY --from=builder /usr/local/bin \
    /usr/local/bin


# Copy application
COPY . .


# Create required folders
RUN mkdir -p uploads logs


# Create non-root user
RUN addgroup --system appgroup && \
    adduser --system --group appuser && \
    chown -R appuser:appgroup /app


USER appuser


# Northflank application port
EXPOSE 8000


# Health check
HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=30s \
    --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1


# Start FastAPI
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]