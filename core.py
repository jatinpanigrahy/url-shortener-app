from collections.abc import Callable

from encoder import generate_short_code
from validator import sanitize_alias, sanitize_url

# Maximum collision retry limit is a safeguard to protect the server from
# entering an infinite loop if hash collisions occur repeatedly.
MAX_COLLISION_RETRIES = 5


def shorten_url(
    raw_url: str,
    custom_alias: str | None = None,
    # using a checker function decouples the core logic from the database
    # implementation, allowing for easier testing and flexibility.
    exists_fn: Callable[[str], bool] | None = None,
) -> tuple[bool, str]:
    if exists_fn is None:
        exists_fn = lambda code: False

    is_valid_url, url_result = sanitize_url(raw_url)
    if not is_valid_url:
        return False, url_result

    clean_url = url_result

    # If a custom alias is already taken, the system terminates with an error
    # immediately, rather than modifying the alias or generating a new one. This
    # ensures that users are aware of the conflict and can choose a different
    # alias.
    if custom_alias is not None:
        is_valid_alias, alias_result = sanitize_alias(custom_alias)
        if not is_valid_alias:
            return False, alias_result

        if exists_fn(alias_result):
            return False, f"Alias '{alias_result}' already exists."

        return True, alias_result

    for attempt in range(MAX_COLLISION_RETRIES):
        salt = "" if attempt == 0 else str(attempt)
        generated_code = generate_short_code(clean_url, salt=salt)

        if not exists_fn(generated_code):
            return True, generated_code

    return False, "Failed to allocate unique code. Collision limit exceeded."


if __name__ == "__main__":
    mock_db = set()
    mock_exists = lambda code: code in mock_db

    ok, res = shorten_url("invalid-url", exists_fn=mock_exists)
    assert not ok
    assert "protocol" in res.lower()

    ok, res = shorten_url(
        "https://example.com", custom_alias="no", exists_fn=mock_exists
    )
    assert not ok
    assert "too short" in res.lower()

    ok, code = shorten_url(
        "https://example.com", custom_alias="my-link", exists_fn=mock_exists
    )
    assert ok
    assert code == "my-link"
    mock_db.add(code)

    ok, res = shorten_url(
        "https://another.com", custom_alias="my-link", exists_fn=mock_exists
    )
    assert not ok
    assert "already exists" in res

    ok, code1 = shorten_url("https://test.com", exists_fn=mock_exists)
    assert ok
    mock_db.add(code1)

    ok, code2 = shorten_url("https://test.com", exists_fn=mock_exists)
    assert ok
    assert code1 != code2

    def saturated_exists(c: str) -> bool:
        return True

    ok, err = shorten_url("https://test.com", exists_fn=saturated_exists)
    assert not ok
    assert "collision limit" in err.lower()

    print("Stage 1 Step 3 core tests passed cleanly.")
