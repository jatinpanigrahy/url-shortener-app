"""
HTTP presentation layer for the URL shortener. The HTTP web presentation
layer for the URL shortener. It exposes RESTful endpoints and handles HTTP
requests and responses. It serves as the interface between clients and the
underlying logic of the URL shortener.
"""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health_check():
    """Operational monitoring endpoint to verify service uptime."""
    return jsonify({"status": "healthy", "service": "url-shortener-api"}), 200


if __name__ == "__main__":
    # Local development server execution
    app.run(host="127.0.0.1", port=5000, debug=True)
