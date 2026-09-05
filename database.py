import os
import sqlite3
from typing import Optional

DATABASE_NAME = "shortener.db"


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
                RETURNING id, original_url, short_code, click_count, created_at, expires_at;
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
            SELECT id, original_url, short_code, click_count, created_at, expires_at
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


def get_user_by_api_key(api_key: str, db_name: str = DATABASE_NAME) -> dict | None:
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
            SELECT original_url, short_code, click_count, created_at, expires_at
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
    """Deletes a short code record from the database.

    Returns True if a row was found and removed, False if no matching record existed.
    """
    conn = get_connection(db_name)
    try:
        cursor = conn.execute("DELETE FROM urls WHERE short_code = ?;", (short_code,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


if __name__ == "__main__":
    test_db = "test_step5.db"

    if os.path.exists(test_db):
        os.remove(test_db)

    init_db(test_db)

    # 1. Create User and Multiple URLs (including TTL record)
    user = create_user("owner@test.com", "hash", "key_abc", db_name=test_db)
    u1 = create_url("https://site-a.com", "code_a", user_id=user["id"], db_name=test_db)
    u2 = create_url(
        "https://site-b.com",
        "code_b",
        user_id=user["id"],
        expires_at="2026-12-31T23:59:59+00:00",
        db_name=test_db,
    )

    # 2. Verify Collection Retrieval
    user_links = get_urls_by_user(user["id"], db_name=test_db)
    assert len(user_links) == 2
    assert user_links[0]["short_code"] in ["code_a", "code_b"]

    # 3. Verify Direct Lookup Returns expires_at
    target_link = get_url_by_code("code_b", db_name=test_db)
    assert target_link is not None
    assert target_link["expires_at"] == "2026-12-31T23:59:59+00:00"

    # 4. Verify Stats Read
    increment_clicks("code_a", db_name=test_db)
    stats = get_url_stats("code_a", db_name=test_db)
    assert stats is not None
    assert stats["click_count"] == 1
    assert stats["original_url"] == "https://site-a.com"

    # 5. Verify Deletion
    assert delete_url_by_code("code_a", db_name=test_db) is True
    assert get_url_by_code("code_a", db_name=test_db) is None

    os.remove(test_db)
    print("Stage 3 Step 5 database TTL & persistence verification passed cleanly.")
