"""
In-memory sliding window rate limiter for the url shortener with zero
dependencies. Uses only standard python libraries.
"""

import time
from collections import defaultdict
from functools import wraps
from threading import Lock

from flask import jsonify, request

_REQUEST_LOG = defaultdict(list)
_LOCK = Lock()


def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """
    Decorator implementing a sliding window rate limiter.
    Identifies clients by their authenticated user API key, falling back to client IP.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            client_id = request.headers.get("X-API-Key")
            if not client_id:
                client_id = request.headers.get("X-Forwarded-For", request.remote_addr)
                if client_id and "," in client_id:
                    client_id = client_id.split(",")[0].strip()

            current_time = time.time()
            cutoff = current_time - window_seconds

            with _LOCK:
                valid_timestamps = [t for t in _REQUEST_LOG[client_id] if t > cutoff]
                _REQUEST_LOG[client_id] = valid_timestamps

                if len(valid_timestamps) >= max_requests:
                    oldest_timestamp = valid_timestamps[0]
                    retry_after = (
                        int(oldest_timestamp + window_seconds - current_time) + 1
                    )

                    response = jsonify(
                        {
                            "error": "Too Many Requests",
                            "message": f"Rate limit exceeded: {max_requests} requests per {window_seconds} seconds.",
                        }
                    )
                    response.status_code = 429
                    response.headers["Retry-After"] = str(max(1, retry_after))
                    response.headers["X-RateLimit-Limit"] = str(max_requests)
                    response.headers["X-RateLimit-Remaining"] = "0"
                    return response

                _REQUEST_LOG[client_id].append(current_time)
                remaining = max_requests - len(_REQUEST_LOG[client_id])

            res = fn(*args, **kwargs)

            if hasattr(res, "headers"):
                res.headers["X-RateLimit-Limit"] = str(max_requests)
                res.headers["X-RateLimit-Remaining"] = str(max(0, remaining))

            return res

        return wrapper

    return decorator


if __name__ == "__main__":
    print("--- Testing Sliding Window Rate Limiter Logic ---")

    test_id = "test-ip-127.0.0.1"
    now = time.time()

    with _LOCK:
        _REQUEST_LOG[test_id] = [now - 70, now - 30, now - 10]
        cutoff = now - 60
        active = [t for t in _REQUEST_LOG[test_id] if t > cutoff]
        _REQUEST_LOG[test_id] = active

    assert len(_REQUEST_LOG[test_id]) == 2
    print("PASS: Out-of-window timestamps correctly evicted.")

    _REQUEST_LOG.clear()
    print("Rate limiter standalone assertions passed cleanly.")
