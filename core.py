"""
Core shortener logic for coordinating URL validation, alias sanitization,
cryptographic encoding, collision mitigation, and persistence to disk.
Integrates with the persistence layer via dependency injection, allowing for
flexible testing and future database backend swaps.
"""

from collections.abc import Callable

import database
from encoder import generate_short_code
from validator import sanitize_alias, sanitize_url

MAX_COLLISION_RETRIES = 5


def default_exists_check(code: str) -> bool:
    return database.get_url_by_code(code) is not None


def default_save_record(
    original_url: str, short_code: str, user_id: int | None
) -> dict:
    return database.create_url(
        original_url=original_url, short_code=short_code, user_id=user_id
    )


def shorten_url(
    raw_url: str,
    custom_alias: str | None = None,
    user_id: int | None = None,
    exists_fn: Callable[[str], bool] = default_exists_check,
    save_fn: Callable[[str, str, int | None], dict] = default_save_record,
) -> tuple[bool, dict | str]:
    is_valid_url, url_result = sanitize_url(raw_url)
    if not is_valid_url:
        return False, url_result

    clean_url = url_result

    if custom_alias is not None:
        is_valid_alias, alias_result = sanitize_alias(custom_alias)
        if not is_valid_alias:
            return False, alias_result

        clean_alias = alias_result

        if exists_fn(clean_alias):
            return False, "Custom alias is already taken."

        saved_record = save_fn(clean_url, clean_alias, user_id)
        return True, saved_record

    salt = 0
    while salt < MAX_COLLISION_RETRIES:
        candidate_code = generate_short_code(clean_url, salt=str(salt))
        if not exists_fn(candidate_code):
            saved_record = save_fn(clean_url, candidate_code, user_id)
            return True, saved_record
        salt += 1

    return False, "Failed to allocate unique short code. Resource saturated."


if __name__ == "__main__":
    import os

    integration_db = "test_integration.db"
    if os.path.exists(integration_db):
        os.remove(integration_db)

    database.init_db(integration_db)

    def test_exists(code: str) -> bool:
        return database.get_url_by_code(code, db_name=integration_db) is not None

    def test_save(url: str, code: str, uid: int | None) -> dict:
        return database.create_url(url, code, user_id=uid, db_name=integration_db)

    # 1. Test standard generation and persistence to disk
    ok, record = shorten_url(
        "https://example.com/integration-test",
        exists_fn=test_exists,
        save_fn=test_save,
    )
    assert ok is True
    assert isinstance(record, dict)
    assert record["original_url"] == "https://example.com/integration-test"
    assert len(record["short_code"]) == 7

    # 2. Test disk-backed collision detection on duplicate custom alias
    ok_alias, alias_record = shorten_url(
        "https://google.com",
        custom_alias="my-link",
        exists_fn=test_exists,
        save_fn=test_save,
    )
    assert ok_alias is True
    assert alias_record["short_code"] == "my-link"

    # Attempt reuse of the exact same alias
    ok_dup, dup_res = shorten_url(
        "https://yahoo.com",
        custom_alias="my-link",
        exists_fn=test_exists,
        save_fn=test_save,
    )
    assert ok_dup is False
    assert dup_res == "Custom alias is already taken."

    # 3. Clean up
    if os.path.exists(integration_db):
        os.remove(integration_db)

    print("Stage 2 Step 3 core-to-database integration passed cleanly.")
