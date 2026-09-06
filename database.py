import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Optional

DATABASE_NAME = os.environ.get("DATABASE_PATH", "shortener.db")


def get_connection(db_name: str = DATABASE_NAME) -> sqlite3.Connection:
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_name: str = DATABASE_NAME) -> None:
    conn = get_connection(db_name)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            original_url TEXT NOT NULL,
            short_code TEXT UNIQUE NOT NULL,
            click_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );
        """
    )

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_urls_short_code ON urls(short_code);"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);")

    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    """Generates a secure PBKDF2-HMAC-SHA256 password hash with an isolated salt."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
    ).hex()
    return f"{salt}${digest}"


def verify_password(stored_password_hash: str, candidate_password: str) -> bool:
    """Validates candidate password against stored salt-digest pair using constant-time evaluation."""
    try:
        salt, original_digest = stored_password_hash.split("$")
        candidate_digest = hashlib.pbkdf2_hmac(
            "sha256", candidate_password.encode("utf-8"), salt.encode("utf-8"), 100000
        ).hex()
        return secrets.compare_digest(original_digest, candidate_digest)
    except (ValueError, AttributeError):
        return False


def generate_api_key() -> str:
    """Generates a cryptographically strong, unguessable API key."""
    return f"usr_{secrets.token_urlsafe(32)}"


def create_user(
    email: str,
    password_hash: str,
    api_key: str,
    db_name: str = DATABASE_NAME,
) -> dict:
    conn = get_connection(db_name)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO users (email, password_hash, api_key)
                VALUES (?, ?, ?)
                RETURNING id, email, api_key, created_at;
                """,
                (email, password_hash, api_key),
            )
            row = cursor.fetchone()
            return dict(row)
    finally:
        conn.close()


def get_user_by_email(email: str, db_name: str = DATABASE_NAME) -> dict | None:
    """Retrieves full user authentication profile by email."""
    conn = get_connection(db_name)
    try:
        cursor = conn.execute(
            """
            SELECT id, email, password_hash, api_key, created_at
            FROM users
            WHERE email = ?;
            """,
            (email.lower().strip(),),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_api_key(api_key: str, db_name: str = DATABASE_NAME) -> dict | None:
    """Retrieves user profile associated with an API key."""
    conn = get_connection(db_name)
    try:
        cursor = conn.execute(
            """
            SELECT id, email, api_key, created_at
            FROM users
            WHERE api_key = ?;
            """,
            (api_key,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_url(
    original_url: str,
    short_code: str,
    user_id: int | None = None,
    expires_at: str | None = None,
    db_name: str = DATABASE_NAME,
) -> dict:
    conn = get_connection(db_name)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO urls (original_url, short_code, user_id, expires_at)
                VALUES (?, ?, ?, ?)
                RETURNING id, original_url, short_code, user_id, click_count, created_at, expires_at;
                """,
                (original_url, short_code, user_id, expires_at),
            )
            row = cursor.fetchone()
            return dict(row)
    finally:
        conn.close()


def get_url_by_code(short_code: str, db_name: str = DATABASE_NAME) -> dict | None:
    conn = get_connection(db_name)
    try:
        cursor = conn.execute(
            """
            SELECT id, original_url, short_code, user_id, click_count, created_at, expires_at
            FROM urls
            WHERE short_code = ?;
            """,
            (short_code,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def increment_clicks(short_code: str, db_name: str = DATABASE_NAME) -> bool:
    conn = get_connection(db_name)
    try:
        with conn:
            cursor = conn.execute(
                """
                UPDATE urls
                SET click_count = click_count + 1
                WHERE short_code = ?;
                """,
                (short_code,),
            )
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_urls_by_user(user_id: int, db_name: str = DATABASE_NAME) -> list[dict]:
    conn = get_connection(db_name)
    try:
        cursor = conn.execute(
            """
            SELECT id, original_url, short_code, click_count, created_at, expires_at
            FROM urls
            WHERE user_id = ?
            ORDER BY created_at DESC;
            """,
            (user_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_url_stats(short_code: str, db_name: str = DATABASE_NAME) -> dict | None:
    conn = get_connection(db_name)
    try:
        cursor = conn.execute(
            """
            SELECT original_url, short_code, user_id, click_count, created_at, expires_at
            FROM urls
            WHERE short_code = ?;
            """,
            (short_code,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_url_by_code(short_code: str, db_name: str = DATABASE_NAME) -> bool:
    conn = get_connection(db_name)
    try:
        cursor = conn.execute("DELETE FROM urls WHERE short_code = ?;", (short_code,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_platform_analytics(db_name: str = DATABASE_NAME) -> dict:
    """
    Executes database-level aggregation to compute platform usage metrics.
    Retrieves top 5 links by click volume and calculates system health ratios.
    """
    conn = get_connection(db_name)
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        top_cursor = conn.execute(
            """
            SELECT short_code, original_url, click_count, created_at, expires_at
            FROM urls
            ORDER BY click_count DESC, created_at DESC
            LIMIT 5;
            """
        )
        top_urls = [dict(row) for row in top_cursor.fetchall()]

        stats_cursor = conn.execute(
            """
            SELECT
                COUNT(*) AS total_links,
                COALESCE(SUM(click_count), 0) AS total_clicks,
                COALESCE(SUM(CASE WHEN expires_at IS NOT NULL AND expires_at <= ? THEN 1 ELSE 0 END), 0) AS expired_links,
                COALESCE(SUM(CASE WHEN expires_at IS NULL OR expires_at > ? THEN 1 ELSE 0 END), 0) AS active_links
            FROM urls;
            """,
            (now_iso, now_iso),
        )
        stats_row = dict(stats_cursor.fetchone())

        user_cursor = conn.execute("SELECT COUNT(*) AS total_users FROM users;")
        user_row = dict(user_cursor.fetchone())

        return {
            "total_links": stats_row["total_links"],
            "total_clicks": stats_row["total_clicks"],
            "total_users": user_row["total_users"],
            "active_links": stats_row["active_links"],
            "expired_links": stats_row["expired_links"],
            "top_5_urls": top_urls,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    test_db = "test_auth_stage5.db"

    if os.path.exists(test_db):
        os.remove(test_db)

    init_db(test_db)

    pwd = "supersecretpassword"
    hash1 = hash_password(pwd)
    hash2 = hash_password(pwd)

    assert hash1 != hash2
    assert verify_password(hash1, pwd) is True
    assert verify_password(hash1, "wrongpassword") is False

    key = generate_api_key()
    assert key.startswith("usr_")
    created_user = create_user("testuser@gdg.org", hash1, key, db_name=test_db)

    user_by_email = get_user_by_email("testuser@gdg.org", db_name=test_db)
    assert user_by_email is not None
    assert user_by_email["id"] == created_user["id"]

    user_by_key = get_user_by_api_key(key, db_name=test_db)
    assert user_by_key is not None
    assert user_by_key["email"] == "testuser@gdg.org"

    u1 = create_url(
        "https://example.com/item1",
        "code1",
        user_id=created_user["id"],
        db_name=test_db,
    )
    assert u1["user_id"] == created_user["id"]

    fetched_u1 = get_url_by_code("code1", db_name=test_db)
    assert fetched_u1 is not None
    assert fetched_u1["user_id"] == created_user["id"]

    user_links = get_urls_by_user(created_user["id"], db_name=test_db)
    assert len(user_links) == 1
    assert user_links[0]["short_code"] == "code1"

    if os.path.exists(test_db):
        os.remove(test_db)

    print("VERIFIED")
