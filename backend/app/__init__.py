import os
from flask import Flask, jsonify
from app.config import config_by_name
from app.extensions import db, migrate, cors
from app.api import api_v1_bp
from app.middleware import init_correlation_middleware
import app.models  # noqa: F401


def create_app(config_name=None):
    """
    Application factory for PharmaPredict AI Flask backend.
    """
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    flask_app = Flask(__name__)
    config_obj = config_by_name.get(config_name, config_by_name["default"])
    flask_app.config.from_object(config_obj)

    # Initialize extensions
    db.init_app(flask_app)
    migrate.init_app(flask_app, db)
    cors.init_app(
        flask_app,
        resources={r"/api/*": {"origins": flask_app.config.get("CORS_ORIGINS", "*")}},
        supports_credentials=True
    )
    init_correlation_middleware(flask_app)

    with flask_app.app_context():
        # Ensure database tables exist
        db.create_all()

    # Register blueprints
    flask_app.register_blueprint(api_v1_bp)

    # Register root diagnostic / health alias
    @flask_app.route("/", methods=["GET"])
    def root_index():
        from flask import request, render_template_string
        # If requested by a web browser, return a rich developer status console
        if "text/html" in request.headers.get("Accept", ""):
            html = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>PharmaPredict AI — Backend Service</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #092342; color: #fff; margin: 0; padding: 40px 20px; display: flex; justify-content: center; align-items: center; min-height: 80vh; }
                    .card { background: #102c50; border: 1px solid rgba(255,255,255,0.15); border-radius: 16px; padding: 36px; max-width: 580px; width: 100%; box-shadow: 0 20px 50px rgba(0,0,0,0.3); }
                    .badge { display: inline-flex; align-items: center; gap: 6px; background: rgba(52, 211, 153, 0.15); color: #34d399; font-size: 12px; font-weight: 700; padding: 4px 12px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.1em; }
                    .dot { width: 8px; height: 8px; border-radius: 50%; background: #34d399; }
                    h1 { margin: 16px 0 8px; font-size: 26px; font-weight: 700; color: #fff; }
                    p { color: #94a3b8; font-size: 14px; line-height: 1.6; margin: 0 0 24px; }
                    .btn-group { display: flex; flex-direction: column; gap: 12px; }
                    .btn { display: block; text-align: center; text-decoration: none; font-weight: 600; font-size: 14px; padding: 12px 20px; border-radius: 10px; transition: all 0.2s; }
                    .btn-primary { background: #1685ff; color: #fff; box-shadow: 0 4px 14px rgba(22, 133, 255, 0.35); }
                    .btn-primary:hover { background: #3a98ff; }
                    .btn-secondary { background: rgba(255,255,255,0.08); color: #e2e8f0; border: 1px solid rgba(255,255,255,0.15); }
                    .btn-secondary:hover { background: rgba(255,255,255,0.15); }
                    .endpoints { margin-top: 24px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 20px; font-size: 12px; color: #64748b; }
                    .endpoints code { color: #61b4ff; font-family: monospace; }
                </style>
            </head>
            <body>
                <div class="card">
                    <span class="badge"><span class="dot"></span> Backend API Online</span>
                    <h1>PharmaPredict AI Backend</h1>
                    <p>The Flask REST API service is active and connected. To interact with the user interface, open the Next.js frontend application below.</p>
                    <div class="btn-group">
                        <a href="http://localhost:3000" class="btn btn-primary" target="_blank">Open Frontend Web App (Port 3000) →</a>
                        <a href="http://localhost:3000/login" class="btn btn-secondary" target="_blank">Open Login Portal (Port 3000)</a>
                        <a href="/api/v1/health" class="btn btn-secondary">Inspect /api/v1/health (JSON)</a>
                    </div>
                    <div class="endpoints">
                        <strong>Active Core API:</strong> <code>GET /api/v1/health</code> &bull; <code>POST /api/v1/auth/login</code> &bull; <code>GET /api/v1/sites</code>
                    </div>
                </div>
            </body>
            </html>
            """
            return render_template_string(html)

        return jsonify({
            "service": flask_app.config.get("APP_NAME", "PharmaPredict AI"),
            "version": flask_app.config.get("APP_VERSION", "0.1.0"),
            "api_documentation": "/api/v1/health",
            "message": "PharmaPredict AI Backend Service is running."
        }), 200

    @flask_app.route("/favicon.ico", methods=["GET"])
    def favicon():
        return "", 204

    # Global error handlers
    @flask_app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "error": "Not Found",
            "message": "The requested endpoint does not exist."
        }), 404

    @flask_app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected server error occurred."
        }), 500

    return flask_app

