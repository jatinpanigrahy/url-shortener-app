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
    return database.get_url_by_code(code) is not None


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


if __name__ == "__main__":
    import os

    test_db = "test_lifecycle.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    database.init_db(test_db)

    def test_exists(code: str) -> bool:
        return database.get_url_by_code(code, db_name=test_db) is not None

    def test_save(url: str, code: str, uid: int | None, exp: str | None = None) -> dict:
        return database.create_url(
            url, code, user_id=uid, expires_at=exp, db_name=test_db
        )

    def test_get(code: str) -> dict | None:
        return database.get_url_by_code(code, db_name=test_db)

    def test_click(code: str) -> bool:
        return database.increment_clicks(code, db_name=test_db)

    ok, record = shorten_url(
        "https://target-domain.com/landing",
        custom_alias="my-promo",
        exists_fn=test_exists,
        save_fn=test_save,
    )
    assert ok is True
    assert record["short_code"] == "my-promo"

    found, destination = resolve_url(
        "my-promo",
        get_fn=test_get,
        click_fn=test_click,
    )
    assert found is True
    assert destination == "https://target-domain.com/landing"

    updated_record = test_get("my-promo")
    assert updated_record["click_count"] == 1

    resolve_url("my-promo", get_fn=test_get, click_fn=test_click)
    updated_record = test_get("my-promo")
    assert updated_record["click_count"] == 2

    bad_found, bad_msg = resolve_url(
        "ghost-code",
        get_fn=test_get,
        click_fn=test_click,
    )
    assert bad_found is False
    assert bad_msg == "URL not found."

    ok_ttl, record_ttl = shorten_url(
        "https://target-domain.com/temp",
        ttl_seconds=1,
        exists_fn=test_exists,
        save_fn=test_save,
    )
    assert ok_ttl is True
    assert record_ttl["expires_at"] is not None

    ok_bool, bool_err = shorten_url(
        "https://target-domain.com/temp",
        ttl_seconds=True,
        exists_fn=test_exists,
        save_fn=test_save,
    )
    assert ok_bool is False
    assert "positive number" in bool_err

    if os.path.exists(test_db):
        os.remove(test_db)

    print("verified core.py")
