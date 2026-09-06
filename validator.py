import re
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}

ALIAS_REGEX = re.compile(r"^[a-zA-Z0-9_-]{3,30}$")

RESERVED_ALIASES = {
    "health",
    "shorten",
    "shortener",
    "analytics",
    "stats",
    "auth",
    "my-urls",
    "api",
    "static",
    "favicon.ico",
    "login",
    "my-links",
    "register",
    "logout",
    "admin",
    "profile",
    "settings",
    "about",
    "top-links",
}


def sanitize_url(raw_url: str) -> tuple[bool, str]:
    if not isinstance(raw_url, str):
        return False, "Input must be a text string."

    cleaned_url = raw_url.strip()

    if not cleaned_url:
        return False, "URL cannot be empty."

    try:
        parsed = urlparse(cleaned_url)
    except ValueError:
        return False, "Malformed URL structure."

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return (
            False,
            f"Invalid protocol '{parsed.scheme}'. Only HTTP and HTTPS are permitted.",
        )

    if not parsed.netloc:
        return (
            False,
            "URL must contain a valid domain (e.g., example.com).",
        )

    blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0"}
    host = parsed.netloc.split(":")[0].lower()

    if host in blocked_hosts or host.endswith((".local", ".internal")):
        return (
            False,
            "Shortening local or loopback addresses is prohibited.",
        )

    if "." not in host:
        return (
            False,
            "URL must contain a valid domain (e.g., example.com).",
        )

    parts = host.split(".")
    tld = parts[-1]
    is_valid_tld = tld.isalpha() and len(tld) >= 2
    is_valid_ipv4 = len(parts) == 4 and all(
        p.isdigit() and 0 <= int(p) <= 255 for p in parts
    )

    if not (is_valid_tld or is_valid_ipv4) or any(not p for p in parts):
        return (
            False,
            "URL must contain a valid domain (e.g., example.com).",
        )

    if not is_valid_ipv4:
        try:
            socket.gethostbyname(host)
        except socket.gaierror:
            return False, f"The domain '{host}' does not exist or cannot be reached."

    return True, cleaned_url


def sanitize_alias(raw_alias: str) -> tuple[bool, str]:
    if not isinstance(raw_alias, str):
        return False, "Alias must be a text string."

    cleaned_alias = raw_alias.strip()

    if not cleaned_alias:
        return False, "Alias cannot be empty."

    if len(cleaned_alias) < 3:
        return False, "Alias is too short (minimum 3 characters)."

    if len(cleaned_alias) > 30:
        return False, "Alias is too long (maximum 30 characters)."

    if not ALIAS_REGEX.match(cleaned_alias):
        return (
            False,
            "Alias contains invalid characters. Use only letters, numbers, hyphens, and underscores.",
        )

    if cleaned_alias.lower() in RESERVED_ALIASES:
        return False, f"The alias '{cleaned_alias}' is a reserved system keyword."

    return True, cleaned_alias


if __name__ == "__main__":
    valid_ok, valid_res = sanitize_url("  https://google.com/search?q=python  ")
    assert valid_ok is True and valid_res == "https://google.com/search?q=python"

    invalid_domain_ok, _ = sanitize_url("https://hey")
    assert invalid_domain_ok is False

    fake_domain_ok, _ = sanitize_url("https://dsfjkdsfjk.com")
    assert fake_domain_ok is False

    xss_ok, _ = sanitize_url("javascript:alert('pwned')")
    assert xss_ok is False

    bad_ok, _ = sanitize_url("http://")
    assert bad_ok is False

    ssrf_ok, _ = sanitize_url("http://localhost:8000/admin")
    assert ssrf_ok is False

    reserved_ok, _ = sanitize_alias("shortener")
    assert reserved_ok is False

    alias_ok, _ = sanitize_alias("valid-alias_123")
    assert alias_ok is True

    alias_bad_ok, _ = sanitize_alias("invalid alias with spaces!")
    assert alias_bad_ok is False

    print("ALL VALIDATOR TESTS PASSED CLEANLY.")
