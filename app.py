"""
HTTP presentation layer for the URL shortener.
"""

import os
import re

from flask import Flask, jsonify, redirect, request

import core
import database

app = Flask(__name__)

ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "my-secret-key-123")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.route("/health", methods=["GET"])
def health_check():
    """Operational monitoring endpoint to verify service uptime."""
    return jsonify({"status": "healthy", "service": "url-shortener-api"}), 200


@app.route("/auth/register", methods=["POST"])
def register():
    """
    Provisions a new user account.
    Hashes the password securely and returns the generated API key.
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
def login():
    """
    Authenticates email and password credentials.
    Returns the user's active API key upon successful authentication.
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


@app.route("/shorten", methods=["POST"])
@app.route("/api/shorten", methods=["POST"])
def shorten():
    """Ingest long URL, optional custom alias, and TTL duration to persist a short code record."""
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

    ok, result = core.shorten_url(
        raw_url=raw_url,
        custom_alias=custom_alias,
        ttl_seconds=ttl_seconds,
    )

    if not ok:
        if result == "Custom alias is already taken.":
            return jsonify({"error": result}), 409
        return jsonify({"error": result}), 400

    record = result
    short_url = f"{request.host_url}{record['short_code']}"
    return jsonify(
        {
            "short_code": record["short_code"],
            "short_url": short_url,
            "original_url": record["original_url"],
            "created_at": record["created_at"],
            "expires_at": record.get("expires_at"),
        }
    ), 201


@app.route("/<short_code>", methods=["GET"])
def redirect_to_url(short_code: str):
    """Resolves short code, validates lifetime boundaries, and redirects visitor to target URL."""
    found, result = core.resolve_url(short_code)

    if not found:
        if result == "URL has expired.":
            return jsonify({"error": "URL has expired.", "short_code": short_code}), 410

        return jsonify({"error": "URL not found.", "short_code": short_code}), 404

    return redirect(result, code=302)


@app.route("/stats/<short_code>", methods=["GET"])
def get_link_stats(short_code: str):
    """Returns analytical metadata for a short code without incrementing click metrics."""
    stats = database.get_url_stats(short_code)
    if stats is None:
        return jsonify({"error": "URL not found.", "short_code": short_code}), 404

    return jsonify(
        {
            "short_code": stats["short_code"],
            "original_url": stats["original_url"],
            "click_count": stats["click_count"],
            "created_at": stats["created_at"],
            "expires_at": stats["expires_at"],
        }
    ), 200


@app.route("/<short_code>", methods=["DELETE"])
def delete_short_link(short_code: str):
    """Deletes an existing mapping from the database. Requires X-API-Key authorization."""
    provided_key = request.headers.get("X-API-Key")
    if not provided_key:
        return jsonify({"error": "Unauthorized. Missing X-API-Key header."}), 401

    if provided_key != ADMIN_API_KEY:
        return jsonify({"error": "Forbidden. Invalid API key."}), 403

    deleted = database.delete_url_by_code(short_code)
    if not deleted:
        return jsonify({"error": "URL not found.", "short_code": short_code}), 404

    return jsonify(
        {"message": f"Short URL '{short_code}' has been successfully deleted."}
    ), 200


if __name__ == "__main__":
    database.init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
