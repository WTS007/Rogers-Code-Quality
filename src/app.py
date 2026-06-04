"""
Nexus Demo API — Flask Application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A demonstration microservice showcasing the Project Nexus AI Code
Quality & Automated Remediation Pipeline. Provides user management,
authentication, and health monitoring endpoints.
"""

import logging
import os
from flask import Flask, jsonify, request, send_from_directory

from src.config import get_config
from src.database import init_db, get_user, search_users, create_user, get_recent_activity
from src.auth import generate_token, validate_token, verify_password, hash_password
from src.utils import sanitize_input, validate_email, generate_request_id, format_timestamp

# ---------------------------------------------------------------------------
# Application Factory
# ---------------------------------------------------------------------------

def create_app(env: str = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        env: Environment name ('development', 'production', 'testing').

    Returns:
        Configured Flask application instance.
    """
    config = get_config(env)

    app = Flask(__name__, static_folder="../static")
    app.config.from_object(config)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("nexus-api")

    # Initialize database
    init_db(config.DATABASE_PATH)

    # Seed a default admin user if table is empty
    if not get_user("admin", config.DATABASE_PATH):
        create_user(
            username="admin",
            email="admin@nexus-demo.local",
            password_hash=hash_password("admin123"),
            role="admin",
            db_path=config.DATABASE_PATH,
        )
        logger.info("Seeded default admin user")

    # -------------------------------------------------------------------
    # CORS Middleware
    # -------------------------------------------------------------------
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["X-Request-ID"] = generate_request_id()
        return response

    # -------------------------------------------------------------------
    # Health & Status
    # -------------------------------------------------------------------
    @app.route("/")
    def index():
        """Serve the status page."""
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/api/health")
    def health_check():
        """Return application health status."""
        return jsonify({
            "status": "healthy",
            "service": "nexus-demo-api",
            "version": "1.0.0",
            "timestamp": format_timestamp(),
            "environment": os.environ.get("APP_ENV", "development"),
        })

    # -------------------------------------------------------------------
    # User Endpoints
    # -------------------------------------------------------------------
    @app.route("/api/users")
    def list_users():
        """List or search users."""
        query = request.args.get("q", "")
        if query:
            users = search_users(sanitize_input(query), config.DATABASE_PATH)
        else:
            users = search_users("", config.DATABASE_PATH)
        return jsonify({"users": users, "count": len(users)})

    @app.route("/api/users", methods=["POST"])
    def register_user():
        """Register a new user."""
        data = request.get_json(silent=True) or {}

        username = sanitize_input(data.get("username", ""))
        email = data.get("email", "")
        password = data.get("password", "")

        if not username or not email or not password:
            return jsonify({"error": "username, email, and password are required"}), 400

        if not validate_email(email):
            return jsonify({"error": "Invalid email format"}), 400

        if get_user(username, config.DATABASE_PATH):
            return jsonify({"error": "Username already exists"}), 409

        user_id = create_user(
            username=username,
            email=email,
            password_hash=hash_password(password),
            db_path=config.DATABASE_PATH,
        )
        return jsonify({"id": user_id, "username": username}), 201

    # -------------------------------------------------------------------
    # Authentication Endpoints
    # -------------------------------------------------------------------
    @app.route("/api/auth/login", methods=["POST"])
    def login():
        """Authenticate a user and return a token."""
        data = request.get_json(silent=True) or {}
        username = data.get("username", "")
        password = data.get("password", "")

        user = get_user(username, config.DATABASE_PATH)
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        if not verify_password(password, user["password_hash"]):
            return jsonify({"error": "Invalid credentials"}), 401

        token = generate_token(user["id"], user["role"])
        logger.info("User '%s' authenticated successfully", username)

        return jsonify({
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
            },
        })

    @app.route("/api/auth/validate", methods=["POST"])
    def validate():
        """Validate an existing token."""
        data = request.get_json(silent=True) or {}
        token = data.get("token", "")

        payload = validate_token(token)
        if payload is None:
            return jsonify({"valid": False, "error": "Token is invalid or expired"}), 401

        return jsonify({"valid": True, "payload": payload})

    # -------------------------------------------------------------------
    # Activity Feed
    # -------------------------------------------------------------------
    @app.route("/api/activity")
    def activity_feed():
        """Return recent audit log entries."""
        limit = request.args.get("limit", 10, type=int)
        events = get_recent_activity(min(limit, 50), config.DATABASE_PATH)
        return jsonify({"events": events, "count": len(events)})

    # -------------------------------------------------------------------
    # VULNERABILITY DEMO ENDPOINTS (6–9)
    # -------------------------------------------------------------------

    @app.route("/api/files/<path:filename>")
    def download_file(filename):
        """Download a file from the uploads directory.

        VULNERABILITY #6: Path Traversal (CWE-22)
        Accepts unsanitized file paths, allowing directory traversal
        attacks (e.g., ../../etc/passwd). Should validate that the
        resolved path stays within the uploads directory.
        """
        # TODO: Validate path is within allowed directory
        uploads_dir = os.path.join(os.getcwd(), "uploads")
        file_path = os.path.join(uploads_dir, filename)
        # No check that file_path is within uploads_dir!
        try:
            with open(file_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            return jsonify({"error": "File not found"}), 404

    @app.route("/api/import-config", methods=["POST"])
    def import_config():
        """Import a serialized configuration object.

        VULNERABILITY #7: Insecure Deserialization (CWE-502)
        Uses pickle.loads() on untrusted user input, which can lead
        to arbitrary code execution. Should use JSON or a safe
        serialization format instead.
        """
        import pickle
        import base64
        # TODO: Replace pickle with JSON deserialization
        data = request.get_data()
        try:
            config_obj = pickle.loads(base64.b64decode(data))
            return jsonify({"imported": True, "keys": list(config_obj.keys())})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/search-preview")
    def search_preview():
        """Render a search results preview page.

        VULNERABILITY #8: Cross-Site Scripting / XSS (CWE-79)
        Reflects user input directly into HTML response without
        escaping, allowing script injection. Should use a template
        engine with auto-escaping or html.escape().
        """
        query = request.args.get("q", "")
        # TODO: Use html.escape() or a template engine with auto-escaping
        html_response = f"""
        <html><body>
        <h2>Search Results for: {query}</h2>
        <p>No results found for <strong>{query}</strong></p>
        </body></html>
        """
        return html_response, 200, {"Content-Type": "text/html"}

    @app.route("/api/debug/info")
    def debug_info():
        """Return application debug information.

        VULNERABILITY #9: Information Exposure Through Debug Info (CWE-489)
        Exposes sensitive internal application state including environment
        variables, file paths, and Python version. Debug endpoints should
        be disabled or require authentication in production.
        """
        import sys
        # TODO: Remove or gate behind authentication before production
        return jsonify({
            "python_version": sys.version,
            "environment": dict(os.environ),
            "cwd": os.getcwd(),
            "sys_path": sys.path,
            "modules_loaded": list(sys.modules.keys())[:50],
        })

    # -------------------------------------------------------------------
    # Error Handlers
    # -------------------------------------------------------------------
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Resource not found", "status": 404}), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error("Internal server error: %s", error)
        return jsonify({"error": "Internal server error", "status": 500}), 500

    return app


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
