# ==============================================================================
# PharmaPredict AI — Flask Backend Multi-Stage Production Dockerfile
# Hardened non-root debian container with Gunicorn WSGI & health probes.
# Zero-cost staging compatible (supports Render Free Tier auto-migration).
# ==============================================================================

# 1. Builder Stage: Compile wheels and dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# 2. Runtime Stage: Minimal production image
FROM python:3.12-slim AS runner

WORKDIR /app

# Install minimal runtime dependencies (libpq for postgres, libgomp1 for OpenMP/scikit-learn, curl for probes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create secure non-root system user, group, and home directory
RUN groupadd --system --gid 10001 appgroup && \
    useradd --system --uid 10001 --gid appgroup --create-home appuser

# Copy installed Python packages from builder to non-root user directory
COPY --from=builder --chown=appuser:appgroup /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app

# Copy application source code
COPY --chown=appuser:appgroup . /app

# Configure executable permissions for container entrypoint
RUN chmod +x /app/entrypoint.sh

# Set production environment defaults
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 5000

# Canonical container health probe (evaluates dynamic PORT or defaults to 5000)
HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT:-5000}/health/live || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]

# Production Gunicorn WSGI server entrypoint with dynamic port and single-worker safety
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers ${GUNICORN_WORKERS:-1} --threads ${GUNICORN_THREADS:-4} --timeout 120 --access-logfile - --error-logfile - run:app"]
