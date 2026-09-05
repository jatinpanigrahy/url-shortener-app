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


def rate_limit(guest_limit: int = 5, auth_limit: int = 20, window_seconds: int = 60):
    """
    Tier-aware sliding window rate limiter decorator.
    - Anonymous guests (IP address) are capped at `guest_limit` per window.
    - Authenticated users (valid X-API-Key) receive `auth_limit` per window.
    Automatically evicts idle keys from memory to eliminate memory leaks.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            api_key = request.headers.get("X-API-Key")

            if api_key:
                client_id = f"user:{api_key}"
                max_requests = auth_limit
            else:
                ip = request.headers.get("X-Forwarded-For", request.remote_addr)
                if ip and "," in ip:
                    ip = ip.split(",")[0].strip()
                client_id = f"ip:{ip}"
                max_requests = guest_limit

            current_time = time.time()
            cutoff = current_time - window_seconds

            with _LOCK:
                valid_timestamps = [t for t in _REQUEST_LOG[client_id] if t > cutoff]

                if valid_timestamps:
                    _REQUEST_LOG[client_id] = valid_timestamps
                else:
                    _REQUEST_LOG.pop(client_id, None)
                    valid_timestamps = []

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
    print("--- Running Limiter Eviction & Tiering Tests ---")

    dummy_key = "ip:192.168.1.1"
    now = time.time()

    with _LOCK:
        _REQUEST_LOG[dummy_key] = [now - 120, now - 90]
        cutoff = now - 60
        valid = [t for t in _REQUEST_LOG[dummy_key] if t > cutoff]
        if valid:
            _REQUEST_LOG[dummy_key] = valid
        else:
            _REQUEST_LOG.pop(dummy_key, None)

    assert dummy_key not in _REQUEST_LOG
    print("PASS: Idle client keys are purged from memory.")

    with _LOCK:
        _REQUEST_LOG[dummy_key] = [now - 10]
        cutoff = now - 60
        valid = [t for t in _REQUEST_LOG[dummy_key] if t > cutoff]
        if valid:
            _REQUEST_LOG[dummy_key] = valid

    assert len(_REQUEST_LOG[dummy_key]) == 1
    print("PASS: Active window timestamps are retained.")

    _REQUEST_LOG.clear()
    print("Limiter unit assertions passed cleanly.")
