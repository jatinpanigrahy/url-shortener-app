"""
HTTP presentation layer for the URL shortener. The HTTP web presentation
layer for the URL shortener. It exposes RESTful endpoints and handles HTTP
requests and responses. It serves as the interface between clients and the
underlying logic of the URL shortener.
"""

from flask import Flask, jsonify, request

import core

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health_check():
    """Operational monitoring endpoint to verify service uptime."""
    return jsonify({"status": "healthy", "service": "url-shortener-api"}), 200


@app.route("/api/shorten", methods=["POST"])
def shorten():
    """
    Ingest long URL and return persisted short code record.
    Enforces payload validation and maps domain results to HTTP status codes.
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

    ok, result = core.shorten_url(raw_url=raw_url, custom_alias=custom_alias)

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
        }
    ), 201


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
