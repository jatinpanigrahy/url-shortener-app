import hashlib
import os
import secrets
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


def get_user_by_email(email: str, db_name: str = DATABASE_NAME) -> Optional[dict]:
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


def get_user_by_api_key(api_key: str, db_name: str = DATABASE_NAME) -> Optional[dict]:
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
