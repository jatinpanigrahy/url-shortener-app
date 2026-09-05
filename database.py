import os
import sqlite3

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
    db_name: str = DATABASE_NAME,
) -> dict:
    conn = get_connection(db_name)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO urls (original_url, short_code, user_id)
                VALUES (?, ?, ?)
                RETURNING id, original_url, short_code, click_count, created_at;
                """,
                (original_url, short_code, user_id),
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
            SELECT id, original_url, short_code, click_count, created_at
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


if __name__ == "__main__":
    test_db = "test_persistence.db"

    if os.path.exists(test_db):
        os.remove(test_db)

    init_db(test_db)

    conn = get_connection(test_db)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users', 'urls');"
    )
    tables = [row["name"] for row in cursor.fetchall()]
    assert "users" in tables
    assert "urls" in tables

    cursor.execute("PRAGMA foreign_keys;")
    fk_active = cursor.fetchone()[0]
    assert fk_active == 1

    conn.close()
    os.remove(test_db)

    init_db(DATABASE_NAME)
    print("Stage 2 Step 1 database initialization passed cleanly.")

if __name__ == "__main__":
    test_db = "test_crud.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    init_db(test_db)

    user = create_user("dev@test.com", "fake_hash", "key_123", db_name=test_db)
    assert user["email"] == "dev@test.com"

    fetched_user = get_user_by_api_key("key_123", db_name=test_db)
    assert fetched_user is not None
    assert fetched_user["id"] == user["id"]

    url = create_url(
        "https://example.com",
        "exmpl01",
        user_id=user["id"],
        db_name=test_db,
    )
    assert url["short_code"] == "exmpl01"

    fetched_url = get_url_by_code("exmpl01", db_name=test_db)
    assert fetched_url is not None
    assert fetched_url["original_url"] == "https://example.com"
    assert fetched_url["click_count"] == 0

    assert increment_clicks("exmpl01", db_name=test_db) is True
    updated_url = get_url_by_code("exmpl01", db_name=test_db)
    assert updated_url["click_count"] == 1

    assert increment_clicks("nonexistent", db_name=test_db) is False

    os.remove(test_db)
    print("Stage 2 Step 2 CRUD tests passed cleanly.")
