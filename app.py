"""
HTTP presentation layer for the URL shortener.
Integrates Multi-Tenant Identity, Row-Level Authorization, Admin Moderation, and RESTful routing.
"""

import os
import re
import secrets
from functools import wraps

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
        print(f"[*] Temporary admin key generated for this session: {ADMIN_API_KEY}")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_authenticated_user() -> dict | None:
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return None
    return database.get_user_by_api_key(api_key)


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return jsonify({"error": "Unauthorized. Missing X-API-Key header."}), 401

        if api_key == ADMIN_API_KEY:
            return fn(*args, **kwargs)

        user = database.get_user_by_api_key(api_key)
        if not user:
            return jsonify({"error": "Forbidden. Invalid API key."}), 403

        if user.get("is_banned"):
            return jsonify({"error": "Forbidden. Account is suspended."}), 403

        if not user.get("is_admin"):
            return jsonify(
                {"error": "Forbidden. Administrator privileges required."}
            ), 403

        return fn(*args, **kwargs)

    return wrapper


@app.route("/", methods=["GET"])
@app.route("/shortener")
@app.route("/my-links")
@app.route("/top-links")
@app.route("/about")
@app.route("/profile")
@app.route("/admin")
def index():
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "url-shortener-api"}), 200


@app.route("/auth/register", methods=["POST"])
@rate_limit(guest_limit=5, auth_limit=5, window_seconds=60)
def register():
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
            "is_admin": bool(user.get("is_admin", 0)),
        }
    ), 201


@app.route("/auth/login", methods=["POST"])
@rate_limit(guest_limit=5, auth_limit=5, window_seconds=60)
def login():
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

    if user.get("is_banned"):
        return jsonify({"error": "Account is suspended. Contact administration."}), 403

    return jsonify(
        {
            "message": "Authentication successful.",
            "user_id": user["id"],
            "email": user["email"],
            "api_key": user["api_key"],
            "is_admin": bool(user.get("is_admin", 0)),
        }
    ), 200


@app.route("/auth/me", methods=["GET"])
def get_current_user_profile():
    user = get_authenticated_user()
    if not user:
        return jsonify(
            {"error": "Unauthorized. A valid user X-API-Key header is required."}
        ), 401

    if user.get("is_banned"):
        return jsonify({"error": "Forbidden. Account is suspended."}), 403

    return jsonify(
        {
            "user_id": user["id"],
            "email": user["email"],
            "created_at": user["created_at"],
            "is_admin": bool(user.get("is_admin", 0)),
        }
    ), 200


@app.route("/shorten", methods=["POST"])
@app.route("/api/shorten", methods=["POST"])
@rate_limit(guest_limit=5, auth_limit=20, window_seconds=60)
def shorten():
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

    user_id = None
    provided_key = request.headers.get("X-API-Key")
    if provided_key:
        auth_user = database.get_user_by_api_key(provided_key)
        if auth_user:
            if auth_user.get("is_banned"):
                return jsonify({"error": "Forbidden. Account is suspended."}), 403
            user_id = auth_user["id"]

    if custom_alias and not user_id:
        return jsonify(
            {
                "error": "Custom link names require an account. Please sign in or register."
            }
        ), 403

    ttl_seconds = payload.get("ttl_seconds")
    if ttl_seconds is not None:
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, (int, float))
            or ttl_seconds <= 0
        ):
            return jsonify(
                {"error": "Field 'ttl_seconds' must be a positive number if provided."}
            ), 400
    else:
        if not user_id:
            ttl_seconds = 14 * 86400

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
    found, result = core.resolve_url(short_code)
    if not found:
        if result == "URL has expired.":
            return jsonify({"error": "URL has expired.", "short_code": short_code}), 410
        return jsonify({"error": "URL not found.", "short_code": short_code}), 404

    return redirect(result, code=302)


@app.route("/stats/<short_code>", methods=["GET"])
def get_link_stats(short_code: str):
    stats = database.get_url_stats(short_code)
    if stats is None:
        return jsonify({"error": "URL not found.", "short_code": short_code}), 404

    if stats.get("user_id"):
        provided_key = request.headers.get("X-API-Key")
        auth_user = database.get_user_by_api_key(provided_key) if provided_key else None
        is_admin = (provided_key == ADMIN_API_KEY) or bool(
            auth_user and auth_user.get("is_admin")
        )
        if not is_admin and (not auth_user or auth_user["id"] != stats["user_id"]):
            return jsonify(
                {
                    "error": "Forbidden. You do not have permission to view stats for this link."
                }
            ), 403

    return jsonify(
        {
            "short_code": stats["short_code"],
            "original_url": stats["original_url"],
            "click_count": stats["click_count"],
            "created_at": stats["created_at"],
            "expires_at": stats["expires_at"],
        }
    ), 200


@app.route("/analytics", methods=["GET"])
def get_analytics():
    analytics_data = database.get_platform_analytics()
    return jsonify(analytics_data), 200


@app.route("/my-urls", methods=["GET"])
def get_my_urls():
    user = get_authenticated_user()
    if not user:
        return jsonify(
            {"error": "Unauthorized. A valid user X-API-Key header is required."}
        ), 401

    if user.get("is_banned"):
        return jsonify({"error": "Forbidden. Account is suspended."}), 403

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
    provided_key = request.headers.get("X-API-Key")
    if not provided_key:
        return jsonify({"error": "Unauthorized. Missing X-API-Key header."}), 401

    stats = database.get_url_stats(short_code)
    if not stats:
        return jsonify({"error": "URL not found.", "short_code": short_code}), 404

    auth_user = database.get_user_by_api_key(provided_key)
    is_admin = (provided_key == ADMIN_API_KEY) or bool(
        auth_user and auth_user.get("is_admin")
    )

    if not is_admin:
        if not auth_user:
            return jsonify({"error": "Forbidden. Invalid API key."}), 403

        if auth_user.get("is_banned"):
            return jsonify({"error": "Forbidden. Account is suspended."}), 403

        if stats.get("user_id") != auth_user["id"]:
            return jsonify(
                {"error": "Forbidden. You do not have permission to delete this URL."}
            ), 403

    database.delete_url_by_code(short_code)
    return jsonify(
        {"message": f"Short URL '{short_code}' has been successfully deleted."}
    ), 200


@app.route("/admin/users", methods=["GET"])
@admin_required
def admin_get_users():
    limit = max(1, min(100, request.args.get("limit", 20, type=int)))
    offset = max(0, request.args.get("offset", 0, type=int))
    search = request.args.get("search", "", type=str).strip()

    data = database.get_users_paginated(limit=limit, offset=offset, search_query=search)
    return jsonify(data), 200


@app.route("/admin/users/<int:user_id>", methods=["GET"])
@admin_required
def admin_get_user_detail(user_id: int):
    user = database.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    return jsonify(user), 200


@app.route("/admin/users/<int:user_id>/toggle-ban", methods=["POST"])
@admin_required
def admin_toggle_user_ban(user_id: int):
    caller = get_authenticated_user()
    if caller and caller["id"] == user_id:
        return jsonify(
            {"error": "Action rejected: You cannot ban your own account."}
        ), 400

    target = database.get_user_by_id(user_id)
    if not target:
        return jsonify({"error": "User not found."}), 404

    updated = database.toggle_user_ban(user_id)
    status_label = "suspended" if updated["is_banned"] else "reactivated"
    return jsonify(
        {
            "message": f"User account has been {status_label}.",
            "user_id": user_id,
            "is_banned": updated["is_banned"],
        }
    ), 200


@app.route("/admin/users/<int:user_id>", methods=["DELETE"])
@admin_required
def admin_delete_user(user_id: int):
    caller = get_authenticated_user()
    if caller and caller["id"] == user_id:
        return jsonify(
            {"error": "Action rejected: You cannot delete your own account."}
        ), 400

    target = database.get_user_by_id(user_id)
    if not target:
        return jsonify({"error": "User not found."}), 404

    database.delete_user_cascade(user_id)
    return jsonify(
        {
            "message": f"User '{target['email']}' and all associated URLs have been purged."
        }
    ), 200


@app.route("/admin/urls", methods=["GET"])
@admin_required
def admin_get_urls():
    limit = max(1, min(100, request.args.get("limit", 20, type=int)))
    offset = max(0, request.args.get("offset", 0, type=int))
    search = request.args.get("search", "", type=str).strip()
    user_id = request.args.get("user_id", None, type=int)

    data = database.get_all_urls_paginated(
        limit=limit, offset=offset, search_query=search, user_id=user_id
    )
    return jsonify(data), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
