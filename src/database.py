"""Database connection and lifecycle management for the URL shortener.

Provides connection pooling semantics, schema initialization, and concurrency
optimizations using SQLite WAL (Write-Ahead Logging) mode.
"""

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

DATABASE_NAME = os.environ.get("DATABASE_PATH", "shortener.db")


def get_connection(db_name: str = DATABASE_NAME) -> sqlite3.Connection:
    """Establish and configure an optimized SQLite connection.

    Enables WAL mode for concurrent readers and writers, enforces foreign key
    constraints, and sets dictionary-style row access.

    Args:
        db_name: Filesystem path to the SQLite database file.

    Returns:
        Configured sqlite3.Connection instance.
    """
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def init_db(db_name: str = DATABASE_NAME) -> None:
    """Initialize database tables and indexes if they do not exist.

    Performs forward-compatible column migrations for existing tables and
    creates necessary lookup indexes for performant queries.

    Args:
        db_name: Filesystem path to the SQLite database file.
    """
    conn = get_connection(db_name)
    cursor = conn.cursor()

    # Core user identity and authentication credentials table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_banned INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # Idempotent forward migrations for existing databases
    cursor.execute("PRAGMA table_info(users);")
    existing_columns = [row["name"] for row in cursor.fetchall()]
    if "is_admin" not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0;")
    if "is_banned" not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0;")

    # Core URL mapping, analytics, and lifecycle table
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
            link_password_hash TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );
        """
    )

    cursor.execute("PRAGMA table_info(urls);")
    existing_url_columns = [row["name"] for row in cursor.fetchall()]
    if "link_password_hash" not in existing_url_columns:
        cursor.execute("ALTER TABLE urls ADD COLUMN link_password_hash TEXT;")

    # Covering indexes for low-latency redirection and API key lookup
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_urls_short_code ON urls(short_code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);")

    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    """Hash a plaintext password using PBKDF2 with a random salt.

    Args:
        password: Raw plaintext password to hash.

    Returns:
        String containing the hex-encoded salt and digest separated by a dollar sign.
    """
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
    ).hex()
    return f"{salt}${digest}"


def verify_password(stored_password_hash: str, candidate_password: str) -> bool:
    """Verify a candidate password against a stored salt and PBKDF2 hash.

    Uses constant-time comparison to prevent timing side-channel attacks.

    Args:
        stored_password_hash: Stored salt and digest in 'salt$digest' format.
        candidate_password: Plaintext password candidate provided by the user.

    Returns:
        True if the candidate matches the stored digest; False otherwise.
    """
    try:
        salt, original_digest = stored_password_hash.split("$")
        candidate_digest = hashlib.pbkdf2_hmac(
            "sha256", candidate_password.encode("utf-8"), salt.encode("utf-8"), 100000
        ).hex()
        return secrets.compare_digest(original_digest, candidate_digest)
    except (ValueError, AttributeError):
        return False


def generate_api_key() -> str:
    """Generate a cryptographically secure random API key.

    Returns:
        Prefixed alphanumeric API key string.
    """
    return f"usr_{secrets.token_urlsafe(32)}"


def create_user(
    email: str,
    password_hash: str,
    api_key: str,
    db_name: str = DATABASE_NAME,
) -> dict:
    """Insert a new user record into the database.

    Args:
        email: Unique user email address.
        password_hash: Hashed password string.
        api_key: Unique API authentication key.
        db_name: Filesystem path to the SQLite database.

    Returns:
        Dictionary representation of the created user row.
    """
    conn = get_connection(db_name)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO users (email, password_hash, api_key, is_admin, is_banned)
                VALUES (?, ?, ?, 0, 0)
                RETURNING id, email, api_key, is_admin, is_banned, created_at;
                """,
                (email, password_hash, api_key),
            )
            row = cursor.fetchone()
            return dict(row)
    finally:
        conn.close()


def get_user_by_email(email: str, db_name: str = DATABASE_NAME) -> dict | None:
    """Retrieve a user record matching the given email address.

    Args:
        email: User email address to query (case-insensitive).
        db_name: Filesystem path to the SQLite database.

    Returns:
        Dictionary containing user details, or None if not found.
    """
    conn = get_connection(db_name)
    try:
        cursor = conn.execute(
            """
            SELECT id, email, password_hash, api_key, is_admin, is_banned, created_at
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
    """Retrieve a user record associated with an API key.

    Args:
        api_key: User API authentication key.
        db_name: Filesystem path to the SQLite database.

    Returns:
        Dictionary containing user details, or None if not found.
    """
    conn = get_connection(db_name)
    try:
        cursor = conn.execute(
            """
            SELECT id, email, api_key, is_admin, is_banned, created_at
            FROM users
            WHERE api_key = ?;
            """,
            (api_key,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int, db_name: str = DATABASE_NAME) -> dict | None:
    """Retrieve user details and aggregated link statistics by user ID.

    Args:
        user_id: Primary key ID of the user.
        db_name: Filesystem path to the SQLite database.

    Returns:
        Dictionary containing user profile and summary metrics, or None if not found.
    """
    conn = get_connection(db_name)
    try:
        cursor = conn.execute(
            """
            SELECT u.id, u.email, u.is_admin, u.is_banned, u.created_at,
                   COUNT(l.id) AS total_links,
                   COALESCE(SUM(l.click_count), 0) AS total_clicks
            FROM users u
            LEFT JOIN urls l ON u.id = l.user_id
            WHERE u.id = ?
            GROUP BY u.id;
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def toggle_user_ban(user_id: int, db_name: str = DATABASE_NAME) -> dict | None:
    """Invert the ban status of a specified user.

    Args:
        user_id: Primary key ID of the target user.
        db_name: Filesystem path to the SQLite database.

    Returns:
        Updated user record, or None if the user does not exist.
    """
    conn = get_connection(db_name)
    try:
        with conn:
            cursor = conn.execute(
                """
                UPDATE users
                SET is_banned = CASE WHEN is_banned = 1 THEN 0 ELSE 1 END
                WHERE id = ?
                RETURNING id, email, is_admin, is_banned, created_at;
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def delete_user_cascade(user_id: int, db_name: str = DATABASE_NAME) -> bool:
    """Delete a user and cascade deletion to all owned short links.

    Args:
        user_id: Primary key ID of the user to delete.
        db_name: Filesystem path to the SQLite database.

    Returns:
        True if the user was deleted; False otherwise.
    """
    conn = get_connection(db_name)
    try:
        with conn:
            conn.execute("DELETE FROM urls WHERE user_id = ?;", (user_id,))
            cursor = conn.execute("DELETE FROM users WHERE id = ?;", (user_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_users_paginated(
    limit: int = 20,
    offset: int = 0,
    search_query: str = "",
    db_name: str = DATABASE_NAME,
) -> dict:
    """Fetch a paginated list of users with search filtering and link counts.

    Args:
        limit: Maximum number of records to return.
        offset: Number of records to skip for pagination.
        search_query: Substring filter matched against email addresses.
        db_name: Filesystem path to the SQLite database.

    Returns:
        Dictionary containing user records, total count, and pagination metadata.
    """
    conn = get_connection(db_name)
    try:
        params = []
        where_clause = ""
        if search_query:
            where_clause = "WHERE u.email LIKE ?"
            params.append(f"%{search_query.lower()}%")

        count_sql = f"SELECT COUNT(*) AS total FROM users u {where_clause};"
        total = conn.execute(count_sql, params).fetchone()["total"]

        query_sql = f"""
            SELECT u.id, u.email, u.is_admin, u.is_banned, u.created_at,
                   COUNT(l.id) AS total_links,
                   COALESCE(SUM(l.click_count), 0) AS total_clicks
            FROM users u
            LEFT JOIN urls l ON u.id = l.user_id
            {where_clause}
            GROUP BY u.id
            ORDER BY u.created_at DESC
            LIMIT ? OFFSET ?;
        """
        query_params = params + [limit, offset]
        cursor = conn.execute(query_sql, query_params)
        users = [dict(row) for row in cursor.fetchall()]

        has_more = (offset + len(users)) < total
        next_offset = offset + len(users) if has_more else None

        return {
            "users": users,
            "total": total,
            "has_more": has_more,
            "next_offset": next_offset,
        }
    finally:
        conn.close()


def get_all_urls_paginated(
    limit: int = 20,
    offset: int = 0,
    search_query: str = "",
    user_id: int | None = None,
    db_name: str = DATABASE_NAME,
) -> dict:
    """Fetch a paginated list of URLs with optional user or keyword filters.

    Args:
        limit: Maximum number of records to return.
        offset: Number of records to skip for pagination.
        search_query: Substring filter matched against short code, target URL, or email.
        user_id: Optional user ID to filter links to a specific owner.
        db_name: Filesystem path to the SQLite database.

    Returns:
        Dictionary containing URL records, total count, and pagination metadata.
    """
    conn = get_connection(db_name)
    try:
        where_clauses = []
        params = []

        if user_id is not None:
            where_clauses.append("l.user_id = ?")
            params.append(user_id)

        if search_query:
            where_clauses.append("(l.short_code LIKE ? OR l.original_url LIKE ? OR u.email LIKE ?)")
            term = f"%{search_query}%"
            params.extend([term, term, term])

        where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_sql = f"""
            SELECT COUNT(*) AS total
            FROM urls l
            LEFT JOIN users u ON l.user_id = u.id
            {where_str};
        """
        total = conn.execute(count_sql, params).fetchone()["total"]

        query_sql = f"""
            SELECT l.id, l.user_id, l.original_url, l.short_code, l.click_count,
                   l.created_at, l.expires_at, u.email AS user_email, (l.link_password_hash IS NOT NULL) AS is_protected
            FROM urls l
            LEFT JOIN users u ON l.user_id = u.id
            {where_str}
            ORDER BY l.created_at DESC
            LIMIT ? OFFSET ?;
        """
        query_params = params + [limit, offset]
        cursor = conn.execute(query_sql, query_params)
        urls = [dict(row) for row in cursor.fetchall()]

        has_more = (offset + len(urls)) < total
        next_offset = offset + len(urls) if has_more else None

        return {
            "urls": urls,
            "total": total,
            "has_more": has_more,
            "next_offset": next_offset,
        }
    finally:
        conn.close()


def is_code_claimable(short_code: str, db_name: str = DATABASE_NAME) -> bool:
    """Determine whether a short code is available for registration or recycling.

    A code is claimable if it either does not exist or expired more than 30
    days ago, past the reclamation grace period.

    Args:
        short_code: Short identifier to evaluate.
        db_name: Filesystem path to the SQLite database.

    Returns:
        True if the short code can be claimed; False otherwise.
    """
    record = get_url_by_code(short_code, db_name=db_name)
    if not record:
        return True

    if not record.get("expires_at"):
        return False

    try:
        exp_date = datetime.fromisoformat(record["expires_at"])
        recycle_threshold = exp_date + timedelta(days=30)
        return datetime.now(timezone.utc) > recycle_threshold
    except ValueError:
        return False


def create_url(
    original_url: str,
    short_code: str,
    user_id: int | None = None,
    expires_at: str | None = None,
    link_password_hash: str | None = None,
    db_name: str = DATABASE_NAME,
) -> dict:
    """Create or overwrite a recycled short URL record.

    If an expired link's code is reclaimed, its metadata and click counts are reset.

    Args:
        original_url: Long destination URL.
        short_code: Unique alphanumeric alias for the destination.
        user_id: Optional ID of the authenticated user creating the link.
        expires_at: Optional ISO 8601 expiration timestamp string.
        link_password_hash: Optional PBKDF2 hash string for password protection.
        db_name: Filesystem path to the SQLite database.

    Returns:
        Dictionary representation of the saved URL record.
    """
    conn = get_connection(db_name)
    try:
        with conn:
            existing = conn.execute(
                "SELECT id, expires_at FROM urls WHERE short_code = ?;",
                (short_code,),
            ).fetchone()

            if existing:
                cursor = conn.execute(
                    """
                    UPDATE urls
                    SET original_url = ?, user_id = ?, click_count = 0,
                        created_at = CURRENT_TIMESTAMP, expires_at = ?, link_password_hash = ?
                    WHERE short_code = ?
                    RETURNING id, original_url, short_code, user_id, click_count, created_at, expires_at, link_password_hash;
                    """,
                    (original_url, user_id, expires_at, link_password_hash, short_code),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO urls (original_url, short_code, user_id, expires_at, link_password_hash)
                    VALUES (?, ?, ?, ?, ?)
                    RETURNING id, original_url, short_code, user_id, click_count, created_at, expires_at, link_password_hash;
                    """,
                    (original_url, short_code, user_id, expires_at, link_password_hash),
                )
            row = cursor.fetchone()
            return dict(row)
    finally:
        conn.close()


def get_url_by_code(short_code: str, db_name: str = DATABASE_NAME) -> dict | None:
    """Fetch URL details for redirection by short code.

    Args:
        short_code: Unique short identifier to look up.
        db_name: Filesystem path to the SQLite database.

    Returns:
        Dictionary representing the URL record, or None if not found.
    """
    conn = get_connection(db_name)
    try:
        cursor = conn.execute(
            """
            SELECT id, original_url, short_code, user_id, click_count, created_at, expires_at, link_password_hash
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
    """Atomically increment the click counter for a short code.

    Args:
        short_code: Short identifier whose count should be incremented.
        db_name: Filesystem path to the SQLite database.

    Returns:
        True if the record was found and updated; False otherwise.
    """
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
    """Retrieve all short URLs created by a specific user.

    Args:
        user_id: Primary key ID of the user.
        db_name: Filesystem path to the SQLite database.

    Returns:
        List of URL record dictionaries ordered by creation time descending.
    """
    conn = get_connection(db_name)
    try:
        cursor = conn.execute(
            """
            SELECT id, original_url, short_code, click_count, created_at, expires_at, (link_password_hash IS NOT NULL) AS is_protected
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
    """Fetch analytics and metadata for a specific short URL.

    Args:
        short_code: Target short code.
        db_name: Filesystem path to the SQLite database.

    Returns:
        Dictionary with URL statistics, or None if not found.
    """
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
    """Delete a short URL record from the database.

    Args:
        short_code: Unique short identifier to delete.
        db_name: Filesystem path to the SQLite database.

    Returns:
        True if the record was found and deleted; False otherwise.
    """
    conn = get_connection(db_name)
    try:
        cursor = conn.execute("DELETE FROM urls WHERE short_code = ?;", (short_code,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_platform_analytics(db_name: str = DATABASE_NAME) -> dict:
    """Aggregate global platform metrics and top-performing links.

    Computes total links, total clicks, active vs expired link counts,
    total registered users, and the top 5 most clicked URLs.

    Args:
        db_name: Filesystem path to the SQLite database.

    Returns:
        Dictionary containing platform aggregate metrics and top URL lists.
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


def update_url_destination(
    short_code: str,
    new_url: str,
    user_id: int | None = None,
    db_name: str = DATABASE_NAME,
) -> dict | None:
    """Update the target destination URL for an existing short code.

    Args:
        short_code: Short identifier whose destination is being updated.
        new_url: New destination URL.
        user_id: Optional user ID for authorization check upstream.
        db_name: Filesystem path to the SQLite database.

    Returns:
        Dictionary representation of the updated URL row, or None if not found.
    """
    conn = get_connection(db_name)
    try:
        with conn:
            cursor = conn.execute(
                """
                UPDATE urls SET original_url = ?
                WHERE short_code = ?
                RETURNING id, original_url, short_code, user_id,
                          click_count, created_at, expires_at;
                """,
                (new_url, short_code),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_url_password_hash(short_code: str, db_name: str = DATABASE_NAME) -> str | None:
    """Retrieve the PBKDF2 password hash for a password-protected link.

    Args:
        short_code: Short identifier to look up.
        db_name: Filesystem path to the SQLite database.

    Returns:
        Stored password hash string, or None if not set or link not found.
    """
    conn = get_connection(db_name)
    try:
        cursor = conn.execute(
            "SELECT link_password_hash FROM urls WHERE short_code = ?;",
            (short_code,),
        )
        row = cursor.fetchone()
        return row["link_password_hash"] if row else None
    finally:
        conn.close()


def verify_link_password(
    short_code: str, candidate_password: str, db_name: str = DATABASE_NAME
) -> bool:
    """Verify a candidate password against a short link's stored password hash.

    Args:
        short_code: Target short code.
        candidate_password: Plaintext candidate password provided by the visitor.
        db_name: Filesystem path to the SQLite database.

    Returns:
        True if the candidate password matches the stored hash; False otherwise.
    """
    stored_hash = get_url_password_hash(short_code, db_name)
    if not stored_hash:
        return False
    return verify_password(stored_hash, candidate_password)

