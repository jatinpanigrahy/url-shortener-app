"""
Core shortener logic for coordinating URL validation, alias sanitization,
cryptographic encoding, collision mitigation, and persistence to disk.
Integrates with the persistence layer via dependency injection, allowing for
flexible testing and future database backend swaps.
"""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import database
from encoder import generate_short_code
from validator import sanitize_alias, sanitize_url

MAX_COLLISION_RETRIES = 5


def default_exists_check(code: str) -> bool:
    return not database.is_code_claimable(code)


def default_save_record(
    original_url: str,
    short_code: str,
    user_id: int | None = None,
    expires_at: str | None = None,
) -> dict:
    return database.create_url(
        original_url=original_url,
        short_code=short_code,
        user_id=user_id,
        expires_at=expires_at,
    )


def shorten_url(
    raw_url: str,
    custom_alias: str | None = None,
    ttl_seconds: int | float | None = None,
    user_id: int | None = None,
    exists_fn: Callable[[str], bool] = default_exists_check,
    save_fn: Callable[[str, str, int | None, str | None], dict] = default_save_record,
) -> tuple[bool, dict | str]:
    is_valid_url, url_result = sanitize_url(raw_url)
    if not is_valid_url:
        return False, url_result

    clean_url = url_result

    expires_at = None
    if ttl_seconds is not None:
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, (int, float))
            or ttl_seconds <= 0
        ):
            return False, "TTL must be a positive number of seconds."
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=int(ttl_seconds))
        ).isoformat(timespec="seconds")

    if custom_alias is not None:
        is_valid_alias, alias_result = sanitize_alias(custom_alias)
        if not is_valid_alias:
            return False, alias_result

        clean_alias = alias_result

        if exists_fn(clean_alias):
            return False, "Custom alias is already taken."

        saved_record = save_fn(clean_url, clean_alias, user_id, expires_at)
        return True, saved_record

    salt = 0
    while salt < MAX_COLLISION_RETRIES:
        candidate_code = generate_short_code(clean_url, salt=str(salt))
        if not exists_fn(candidate_code):
            saved_record = save_fn(clean_url, candidate_code, user_id, expires_at)
            return True, saved_record
        salt += 1

    return False, "Failed to allocate unique short code. Resource saturated."


def default_get_record(code: str) -> dict | None:
    return database.get_url_by_code(code)


def default_increment_clicks(code: str) -> bool:
    return database.increment_clicks(code)


def resolve_url(
    short_code: str,
    get_fn: Callable[[str], dict | None] = default_get_record,
    click_fn: Callable[[str], bool] = default_increment_clicks,
) -> tuple[bool, str]:
    record = get_fn(short_code)
    if record is None:
        return False, "URL not found."

    if record.get("expires_at"):
        try:
            expiration_date = datetime.fromisoformat(record["expires_at"])
            if datetime.now(timezone.utc) > expiration_date:
                return False, "URL has expired."
        except ValueError:
            pass

    click_fn(short_code)
    return True, record["original_url"]
