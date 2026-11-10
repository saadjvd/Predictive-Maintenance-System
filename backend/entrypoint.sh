#!/bin/sh
set -e

# ==============================================================================
# PharmaPredict AI — Container Entrypoint
# Executes pre-flight database migrations before launching Gunicorn WSGI.
# Compatible with Render Free Tier ($0/mo, no preDeployCommand hook).
# ==============================================================================

if [ -n "$DATABASE_URL" ] && [ "$SKIP_STARTUP_MIGRATIONS" != "true" ]; then
    echo "[entrypoint] Executing pre-flight database migration check..."
    python scripts/deploy_migrations.py || {
        echo "[entrypoint] Pre-flight database migration failed. Aborting startup."
        exit 1
    }
fi

exec "$@"
