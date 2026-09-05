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
