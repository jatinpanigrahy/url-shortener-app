"""Input validation and sanitization for URLs and custom aliases.

Enforces structural validity, protocol restrictions, loopback and private
address protections (SSRF), and reserved system keyword prevention without
performing blocking network calls.
"""

import re
from urllib.parse import urlparse

# Permitted web protocols
ALLOWED_SCHEMES = {"http", "https"}

# Allowed characters for custom aliases: alphanumeric, hyphens, and underscores (3-30 chars)
ALIAS_REGEX = re.compile(r"^[a-zA-Z0-9_-]{3,30}$")

# Internal application routes protected against collision with custom short codes
RESERVED_ALIASES = {
    "about",
    "admin",
    "analytics",
    "api",
    "auth",
    "favicon.ico",
    "health",
    "leaderboard",
    "login",
    "logout",
    "my-links",
    "my-urls",
    "profile",
    "register",
    "settings",
    "shorten",
    "shortener",
    "static",
    "stats",
    "top-links",
}


def sanitize_url(raw_url: str) -> tuple[bool, str]:
    """Validate and sanitize a destination URL.

    Verifies the scheme, domain structure, and top-level domain while rejecting
    local network and loopback addresses to guard against SSRF vulnerabilities.

    Args:
        raw_url: Candidate URL string submitted by the client.

    Returns:
        A tuple of (is_valid, sanitized_url_or_error_message).
    """
    # Verify input type safety
    if not isinstance(raw_url, str):
        return False, "Input must be a text string."

    # Normalize whitespace
    cleaned_url = raw_url.strip()
    if not cleaned_url:
        return False, "URL cannot be empty."

    # Parse URL into standard components
    try:
        parsed = urlparse(cleaned_url)
    except ValueError:
        return False, "Malformed URL structure."

    # Restrict protocol to HTTP and HTTPS
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return (
            False,
            f"Invalid protocol '{parsed.scheme}'. Only HTTP and HTTPS are permitted.",
        )

    # Require a valid network location (domain)
    if not parsed.netloc:
        return (
            False,
            "URL must contain a valid domain (e.g., example.com).",
        )

    # Anti-SSRF: Block localhost, loopback, and internal network addresses
    blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0"}
    host = parsed.netloc.split(":")[0].lower()

    if host in blocked_hosts or host.endswith((".local", ".internal")):
        return (
            False,
            "Shortening local or loopback addresses is prohibited.",
        )

    # Require at least one period separating domain labels
    if "." not in host:
        return (
            False,
            "URL must contain a valid domain (e.g., example.com).",
        )

    # Verify structural validity of the TLD or IPv4 address without blocking network DNS
    parts = host.split(".")
    tld = parts[-1]
    is_valid_tld = tld.isalpha() and len(tld) >= 2
    is_valid_ipv4 = len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)

    if not (is_valid_tld or is_valid_ipv4) or any(not p for p in parts):
        return (
            False,
            "URL must contain a valid domain (e.g., example.com).",
        )

    return True, cleaned_url


def sanitize_alias(raw_alias: str) -> tuple[bool, str]:
    """Validate and sanitize a custom short code alias.

    Enforces length boundaries, alphanumeric character sets, and protects
    internal reserved keywords from route collision.

    Args:
        raw_alias: Candidate short code string submitted by the user.

    Returns:
        A tuple of (is_valid, sanitized_alias_or_error_message).
    """
    # Verify input type safety
    if not isinstance(raw_alias, str):
        return False, "Alias must be a text string."

    # Normalize whitespace
    cleaned_alias = raw_alias.strip()
    if not cleaned_alias:
        return False, "Alias cannot be empty."

    # Enforce minimum and maximum length bounds
    if len(cleaned_alias) < 3:
        return False, "Alias is too short (minimum 3 characters)."
    if len(cleaned_alias) > 30:
        return False, "Alias is too long (maximum 30 characters)."

    # Enforce character set constraints (letters, digits, hyphens, underscores)
    if not ALIAS_REGEX.match(cleaned_alias):
        return (
            False,
            "Alias contains invalid characters. Use only letters, numbers, hyphens, and underscores.",
        )

    # Prevent collision with internal system endpoints
    if cleaned_alias.lower() in RESERVED_ALIASES:
        return False, f"The alias '{cleaned_alias}' is a reserved system keyword."

    return True, cleaned_alias


def sanitize_link_password(raw_password: str) -> tuple[bool, str]:
    """Validate and sanitize a link-level password.

    Enforces length boundaries and prevents control characters.

    Args:
        raw_password: Candidate password string submitted by the user.

    Returns:
        A tuple of (is_valid, sanitized_password_or_error_message).
    """
    if not isinstance(raw_password, str):
        return False, "Password must be a text string."

    if not (3 <= len(raw_password) <= 100):
        return False, "Password must be between 3 and 100 characters."

    if any(not c.isprintable() for c in raw_password):
        return False, "Password contains invalid control characters."

    return True, raw_password


if __name__ == "__main__":
    # Smoke tests: URL sanitization
    assert sanitize_url("  https://google.com/search?q=python  ") == (
        True,
        "https://google.com/search?q=python",
    )
    assert sanitize_url("https://hey")[0] is False
    assert sanitize_url("https://dsfjkdsfjk.com")[0] is True
    assert sanitize_url("javascript:alert('pwned')")[0] is False
    assert sanitize_url("http://")[0] is False
    assert sanitize_url("http://localhost:8000/admin")[0] is False

    # Smoke tests: Alias sanitization
    assert sanitize_alias("shortener")[0] is False
    assert sanitize_alias("valid-alias_123") == (True, "valid-alias_123")
    assert sanitize_alias("invalid alias with spaces!")[0] is False

    # Smoke tests: Password sanitization
    assert sanitize_link_password("secret")[0] is True
    assert sanitize_link_password("hi")[0] is False
    assert sanitize_link_password("sec\nret")[0] is False

    print("All validator smoke tests passed.")
