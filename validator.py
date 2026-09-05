import re
from urllib.parse import urlparse

# A strict whitelist (http and https only) is used to prevent SSRF attacks and
# other malicious URL schemes.
ALLOWED_SCHEMES = {"http", "https"}

# Custom aliases are restricted to alphanumeric characters, hyphens, and
# underscores, so that they do not break browser URLs or collide with routing
# symbols. The length is limited to a reasonable range to prevent abuse and
# ensure usability.
ALIAS_REGEX = re.compile(r"^[a-zA-Z0-9_-]{3,30}$")


def sanitize_url(raw_url: str) -> tuple[bool, str]:
    """
    Validates an incoming URL against protocol and structure rules. Returns:
    (is_valid: bool, error_message_or_cleaned_url: str)
    """
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

    # Blocking localhost and loopback addresses prevents SSRF (server-side
    # request forgery) attacks and other malicious uses of the URL shortener.
    blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0"}
    host = parsed.netloc.split(":")[0].lower()
    if host in blocked_hosts:
        return (
            False,
            "Shortening local or loopback addresses is prohibited.",
        )

    return True, cleaned_url


def sanitize_alias(raw_alias: str) -> tuple[bool, str]:
    """
    Validates a requested custom short code.
    Returns: (is_valid: bool, error_message_or_cleaned_alias: str)
    """
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

    return True, cleaned_alias


if __name__ == "__main__":
    print("--- Running Validator Verification Tests ---")

    valid_ok, valid_res = sanitize_url("  https://google.com/search?q=python  ")
    assert valid_ok is True and valid_res == "https://google.com/search?q=python"
    print("PASS: Standard HTTPS URL sanitization")

    xss_ok, xss_msg = sanitize_url("javascript:alert('pwned')")
    assert xss_ok is False
    print(f"PASS: Rejected malicious scheme -> {xss_msg}")

    bad_ok, bad_msg = sanitize_url("http://")
    assert bad_ok is False
    print(f"PASS: Rejected empty domain -> {bad_msg}")

    ssrf_ok, ssrf_msg = sanitize_url("http://localhost:8000/admin")
    assert ssrf_ok is False
    print(f"PASS: Rejected loopback attempt -> {ssrf_msg}")

    alias_ok, _ = sanitize_alias("valid-alias_123")
    assert alias_ok is True
    print("PASS: Valid custom alias accepted")

    alias_bad_ok, alias_msg = sanitize_alias("invalid alias with spaces!")
    assert alias_bad_ok is False
    print(f"PASS: Rejected malformed alias -> {alias_msg}")

    print("\nALL VALIDATOR TESTS PASSED CLEANLY.")
