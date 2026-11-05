"""Correlation ID and Security Headers Middleware for Pharmaceutical Auditability."""
import uuid
import logging
from flask import request, g

logger = logging.getLogger(__name__)


def get_correlation_id() -> str:
    """Returns the current request's correlation ID or generates a fallback ID."""
    try:
        if hasattr(g, "correlation_id") and g.correlation_id:
            return g.correlation_id
    except RuntimeError:
        # Outside of application context
        pass
    return str(uuid.uuid4())


def init_correlation_middleware(app):
    """Initializes correlation ID tracking and security response headers."""

    @app.before_request
    def set_correlation_id():
        # Read header or generate new correlation ID
        incoming_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID")
        g.correlation_id = incoming_id if incoming_id else str(uuid.uuid4())

    @app.after_request
    def set_security_and_correlation_headers(response):
        # 1. Attach Correlation ID for end-to-end tracing
        if hasattr(g, "correlation_id"):
            response.headers["X-Correlation-ID"] = g.correlation_id

        # 2. Attach Standard Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response

