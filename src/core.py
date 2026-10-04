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
from validator import sanitize_alias, sanitize_link_password, sanitize_url

MAX_COLLISION_RETRIES = 5


def default_exists_check(code: str) -> bool:
    return not database.is_code_claimable(code)


def default_save_record(
    original_url: str,
    short_code: str,
    user_id: int | None = None,
    expires_at: str | None = None,
    link_password_hash: str | None = None,
) -> dict:
    return database.create_url(
        original_url=original_url,
        short_code=short_code,
        user_id=user_id,
        expires_at=expires_at,
        link_password_hash=link_password_hash,
    )


def default_hash_password(pwd: str) -> str:
    return database.hash_password(pwd)


def shorten_url(
    raw_url: str,
    custom_alias: str | None = None,
    ttl_seconds: int | float | None = None,
    user_id: int | None = None,
    link_password: str | None = None,
    exists_fn: Callable[[str], bool] = default_exists_check,
    save_fn: Callable[[str, str, int | None, str | None, str | None], dict] = default_save_record,
    hash_fn: Callable[[str], str] = default_hash_password,
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

    pwd_hash = None
    if link_password is not None:
        is_valid_pwd, pwd_result = sanitize_link_password(link_password)
        if not is_valid_pwd:
            return False, pwd_result
        pwd_hash = hash_fn(pwd_result)

    if custom_alias is not None:
        is_valid_alias, alias_result = sanitize_alias(custom_alias)
        if not is_valid_alias:
            return False, alias_result

        clean_alias = alias_result

        if exists_fn(clean_alias):
            return False, "Custom alias is already taken."

        saved_record = save_fn(clean_url, clean_alias, user_id, expires_at, pwd_hash)
        return True, saved_record

    salt = 0
    while salt < MAX_COLLISION_RETRIES:
        candidate_code = generate_short_code(clean_url, salt=str(salt))
        if not exists_fn(candidate_code):
            saved_record = save_fn(clean_url, candidate_code, user_id, expires_at, pwd_hash)
            return True, saved_record
        salt += 1

    return False, "Failed to allocate unique short code. Resource saturated."


def default_get_record(code: str) -> dict | None:
    return database.get_url_by_code(code)


def default_increment_clicks(code: str) -> bool:
    return database.increment_clicks(code)


def default_verify_password(stored_password_hash: str, candidate_password: str) -> bool:
    return database.verify_password(stored_password_hash, candidate_password)


def resolve_url(
    short_code: str,
    provided_password: str | None = None,
    get_fn: Callable[[str], dict | None] = default_get_record,
    click_fn: Callable[[str], bool] = default_increment_clicks,
    verify_fn: Callable[[str, str], bool] = default_verify_password,
    **kwargs,
) -> tuple[bool, str]:
    if callable(provided_password):
        get_fn = provided_password
        provided_password = None
    if "verify_password_fn" in kwargs:
        verify_fn = kwargs["verify_password_fn"]

    record = get_fn(short_code)
    if record is None:
        return False, "URL not found."

    if record.get("expires_at"):
        try:
            expiration_date = datetime.fromisoformat(record["expires_at"])
            if expiration_date.tzinfo is None:
                expiration_date = expiration_date.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expiration_date:
                return False, "URL has expired."
        except (ValueError, TypeError):
            pass

    if record.get("link_password_hash"):
        if not provided_password or not verify_fn(record["link_password_hash"], provided_password):
            return False, "Password required or invalid."

    click_fn(short_code)
    return True, record["original_url"]


def default_update_destination(code: str, new_url: str) -> dict | None:
    return database.update_url_destination(code, new_url)


def edit_url_destination(
    short_code: str,
    new_url: str,
    user: dict | None,
    is_admin: bool = False,
    get_fn: Callable[[str], dict | None] = default_get_record,
    update_fn: Callable[[str, str], dict | None] = default_update_destination,
) -> tuple[bool, dict | str]:
    record = get_fn(short_code)
    if record is None:
        return False, "URL not found."

    if not is_admin:
        if not user:
            return False, "Forbidden. Invalid API key."
        if user.get("is_banned"):
            return False, "Forbidden. Account is suspended."
        if record.get("user_id") != user.get("id"):
            return False, "Forbidden. You do not have permission to edit this URL."

    is_valid, url_result = sanitize_url(new_url)
    if not is_valid:
        return False, url_result

    updated_record = update_fn(short_code, url_result)
    if not updated_record:
        return False, "Failed to update URL."

    return True, updated_record
