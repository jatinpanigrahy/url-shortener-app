"""
HTTP presentation layer for the URL shortener.
Integrates Multi-Tenant Identity, Row-Level Authorization, and RESTful routing.
"""

import os
import re
import secrets

from flask import Flask, jsonify, redirect, render_template, request

import core
import database
from limiter import rate_limit

app = Flask(__name__)

database.init_db()

ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY")
if not ADMIN_API_KEY:
    ADMIN_API_KEY = secrets.token_urlsafe(32)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        print(f"[*] WARNING: No ADMIN_API_KEY set in environment.")
        print(f"[*] Ephemeral admin key generated for this session: {ADMIN_API_KEY}")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_authenticated_user() -> dict | None:
    """Helper to resolve a requesting user identity via the X-API-Key header."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return None
    return database.get_user_by_api_key(api_key)


@app.route("/", methods=["GET"])
def index():
    """Renders the responsive web client dashboard."""
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health_check():
    """Operational monitoring endpoint to verify service uptime."""
    return jsonify({"status": "healthy", "service": "url-shortener-api"}), 200


@app.route("/auth/register", methods=["POST"])
@rate_limit(guest_limit=5, auth_limit=5, window_seconds=60)
def register():
    """
    Provisions a new user account and returns an API key.
    Rate limited to 5 registration requests per minute per IP.
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Invalid or missing JSON payload."}), 400

    email = payload.get("email")
    password = payload.get("password")

    if not email or not isinstance(email, str) or not EMAIL_REGEX.match(email.strip()):
        return jsonify({"error": "A valid email address is required."}), 400

    if not password or not isinstance(password, str) or len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters long."}), 400

    clean_email = email.strip().lower()

    if database.get_user_by_email(clean_email):
        return jsonify({"error": "An account with this email already exists."}), 409

    pwd_hash = database.hash_password(password)
    new_key = database.generate_api_key()

    user = database.create_user(
        email=clean_email, password_hash=pwd_hash, api_key=new_key
    )
    return jsonify(
        {
            "message": "User registered successfully.",
            "user_id": user["id"],
            "email": user["email"],
            "api_key": user["api_key"],
        }
    ), 201


@app.route("/auth/login", methods=["POST"])
@rate_limit(guest_limit=5, auth_limit=5, window_seconds=60)
def login():
    """
    Authenticates credentials and returns the active API key.
    Rate limited to 5 login attempts per minute to block brute-force attacks.
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Invalid or missing JSON payload."}), 400

    email = payload.get("email")
    password = payload.get("password")

    if (
        not email
        or not password
        or not isinstance(email, str)
        or not isinstance(password, str)
    ):
        return jsonify(
            {"error": "Both 'email' and 'password' are required strings."}
        ), 400

    clean_email = email.strip().lower()
    user = database.get_user_by_email(clean_email)

    if not user or not database.verify_password(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401

    return jsonify(
        {
            "message": "Authentication successful.",
            "user_id": user["id"],
            "api_key": user["api_key"],
        }
    ), 200


@app.route("/auth/me", methods=["GET"])
def get_current_user_profile():
    """
    Returns profile information for the authenticated user.
    Requires a valid X-API-Key header.
    """
    user = get_authenticated_user()
    if not user:
        return jsonify(
            {"error": "Unauthorized. A valid user X-API-Key header is required."}
        ), 401

    return jsonify(
        {
            "user_id": user["id"],
            "email": user["email"],
            "created_at": user["created_at"],
        }
    ), 200


@app.route("/shorten", methods=["POST"])
@app.route("/api/shorten", methods=["POST"])
@rate_limit(guest_limit=5, auth_limit=20, window_seconds=60)
def shorten():
    """
    Ingests long URL and creates short code mapping.
    Rate limited: 5 req/min for guests, 20 req/min for authenticated accounts.
    """
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Invalid or missing JSON payload."}), 400

    raw_url = payload.get("url")
    if not raw_url or not isinstance(raw_url, str):
        return jsonify({"error": "Field 'url' is required and must be a string."}), 400

    custom_alias = payload.get("custom_alias")
    if custom_alias is not None and not isinstance(custom_alias, str):
        return jsonify(
            {"error": "Field 'custom_alias' must be a string if provided."}
        ), 400

    ttl_seconds = payload.get("ttl_seconds")
    if ttl_seconds is not None and (
        isinstance(ttl_seconds, bool)
        or not isinstance(ttl_seconds, (int, float))
        or ttl_seconds <= 0
    ):
        return jsonify(
            {"error": "Field 'ttl_seconds' must be a positive number if provided."}
        ), 400

    user_id = None
    provided_key = request.headers.get("X-API-Key")
    if provided_key:
        auth_user = database.get_user_by_api_key(provided_key)
        if auth_user:
            user_id = auth_user["id"]

    ok, result = core.shorten_url(
        raw_url=raw_url,
        custom_alias=custom_alias,
        ttl_seconds=ttl_seconds,
        user_id=user_id,
    )

    if not ok:
        if result == "Custom alias is already taken.":
            return jsonify({"error": result}), 409
        if "Resource saturated" in result:
            return jsonify({"error": result}), 409
        return jsonify({"error": result}), 400

    record = result
    short_url = f"{request.host_url}{record['short_code']}"
    return jsonify(
        {
            "short_code": record["short_code"],
            "short_url": short_url,
            "original_url": record["original_url"],
            "user_id": record.get("user_id"),
            "created_at": record["created_at"],
            "expires_at": record.get("expires_at"),
        }
    ), 201


@app.route("/<short_code>", methods=["GET"])
def redirect_to_url(short_code: str):
    """Resolves short code and redirects visitor to destination target."""
    found, result = core.resolve_url(short_code)
    if not found:
        if result == "URL has expired.":
            return jsonify({"error": "URL has expired.", "short_code": short_code}), 410
        return jsonify({"error": "URL not found.", "short_code": short_code}), 404

    return redirect(result, code=302)


@app.route("/stats/<short_code>", methods=["GET"])
def get_link_stats(short_code: str):
    """Returns analytics metadata without mutating click counts."""
    stats = database.get_url_stats(short_code)
    if stats is None:
        return jsonify({"error": "URL not found.", "short_code": short_code}), 404

    return jsonify(
        {
            "short_code": stats["short_code"],
            "original_url": stats["original_url"],
            "user_id": stats.get("user_id"),
            "click_count": stats["click_count"],
            "created_at": stats["created_at"],
            "expires_at": stats["expires_at"],
        }
    ), 200


@app.route("/analytics", methods=["GET"])
def get_analytics():
    """
    Returns platform-wide diagnostic metrics:
    total links, total clicks, active vs. expired ratios, and the top 5 most-clicked links.
    """
    analytics_data = database.get_platform_analytics()
    return jsonify(analytics_data), 200


@app.route("/my-urls", methods=["GET"])
def get_my_urls():
    """
    Returns all URLs owned by the authenticated caller.
    Requires a valid user X-API-Key header.
    """
    user = get_authenticated_user()
    if not user:
        return jsonify(
            {"error": "Unauthorized. A valid user X-API-Key header is required."}
        ), 401

    urls = database.get_urls_by_user(user["id"])
    return jsonify(
        {
            "user_id": user["id"],
            "email": user["email"],
            "total_urls": len(urls),
            "urls": urls,
        }
    ), 200


@app.route("/<short_code>", methods=["DELETE"])
def delete_short_link(short_code: str):
    """
    Deletes an existing mapping.
    Enforces Row-Level Access Control (RLAC):
      - Master ADMIN_API_KEY can delete any link.
      - Regular users can ONLY delete links matching their user_id.
    """
    provided_key = request.headers.get("X-API-Key")
    if not provided_key:
        return jsonify({"error": "Unauthorized. Missing X-API-Key header."}), 401

    stats = database.get_url_stats(short_code)
    if not stats:
        return jsonify({"error": "URL not found.", "short_code": short_code}), 404

    is_admin = provided_key == ADMIN_API_KEY
    auth_user = database.get_user_by_api_key(provided_key)

    if not is_admin:
        if not auth_user:
            return jsonify({"error": "Forbidden. Invalid API key."}), 403

        if stats.get("user_id") != auth_user["id"]:
            return jsonify(
                {"error": "Forbidden. You do not have permission to delete this URL."}
            ), 403

    database.delete_url_by_code(short_code)
    return jsonify(
        {"message": f"Short URL '{short_code}' has been successfully deleted."}
    ), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
