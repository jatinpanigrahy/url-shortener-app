# URL Shortener

> **Live Deployment:** [https://jatinpanigrahy.pythonanywhere.com](https://jatinpanigrahy.pythonanywhere.com)

A lightweight, reliable URL shortener built with Python 3, Flask, and SQLite. It generates compact 7-character alphanumeric codes for long URLs, handles hash collisions gracefully, and provides a secure multi-user API with rate limiting and analytics. 
The code is designed natively in Python without relying on external dependencies for core functionality, making it very efficient and easy to deploy. 

---

## Features

* **Custom Base62 Short Codes:** Converts long URLs into compact 7-character alphanumeric codes, with optional custom aliases.
* **Collision Handling:** Uses SHA-256 hashing with an incremental salting loop to resolve collisions automatically.
* **Expiration & TTL:** Users can set a time-to-live (TTL) for each short URL, after which it expires and returns a `410 Gone` status.
* **Multi-User Support:** Users can register, log in, and manage their own short URLs.Passwords are securely hashed with PBKDF2 and each user receives a unique API key for authentication.
* **Row-Level Access Control:** Users can only delete or view statistics for their own links, while admins can manage all links.
* **Rate Limiting:** A custom sliding-window rate limiter built with Python's standard library (`threading.Lock` and `collections.defaultdict`) restricts anonymous users to 5 requests/minute and authenticated users to 20 requests/minute.
* **Platform Analytics Dashboard:** Provides global statistics on total links, clicks, users, and the top 5 most-clicked URLs using an SQL-aggregated metrics endpoint.
* **Input Validation & Security:** Enforces strict URL whitelisting (`http`, `https`), validates custom aliases, and blocks security threats like SSRF, XSS, and SQL injection. All user inputs are sanitized and validated before processing.

---

## Design Decisions

### 1. Base62 vs. Hexadecimal vs. Base64
* **Hexadecimal(Base16):** Only uses 16 characters (`0-9`, `a-f`). A 7-character hex code only provides $16^7$ = `268,435,456` unique combinations, which is insufficient.
* **Base64:** Uses 64 characters (`0-9`, `a-z`, `A-Z`, `+`, `/`). While it provides significantly more combinations ( $64^7$ = `4,398,046,511,104` ), the special characters `+` and `/` have special meanings in URLs and require encoding, making links less user-friendly.
* **Base62:** Uses 62 characters (`0-9`, `a-z`, `A-Z`). A 7-character Base62 code yields over **3.5 trillion** unique combinations ( $62^7$ = `3,521,614,606,208` ), giving huge scalability while remaining URL-safe and user-friendly. This makes Base62 the optimal choice for generating short codes.

### 2. Collision Handling
Hashing an infinite number of URLs into a finite 7-character code space will inevitably produce collisions over time. 
1. The system uses SHA-256 to hash the original URL and the first 12 hex characters are converted to Base62 to create a 7-character code.
2. The database checks if the generated code already exists. 
3. If it is taken, the system appends a numeric counter to the original URL (e.g., `url + "1"`, `url + "2"`, etc.) and rehashes until a unique code is found. 
4. SHA-256's hashing ensures that just a single character change generates a completely different short code, minimizing the chance of repeated collisions.
5. The loop retries upto 5 times before stopping to prevent infinite loops, and returns a `409 Conflict` error if no unique code can be generated.

### 3. HTTP 302 Found vs. 301 Moved Permanently
The redirect route uses `HTTP 302 Found` instead of `301 Moved Permanently` for the following reasons:
1. **Dynamic Behavior:** The short URL may expire or be deleted, so a permanent redirect would mislead clients into caching the URL indefinitely.
2. **User Control:** Users may want to change the destination URL for a given short code, which is not possible with a permanent redirect.
3. **Analytics Tracking:** An HTTP 301 redirect is permanently cached by web browsers, meaning future visits would bypass the server and break click tracking. Using a 302 redirect ensures that every click is logged and counted in the analytics dashboard.

### 4. Rate Limiting
The rate limiter is implemented natively in Python in `limiter.py` using standard library tools: 
* **Sliding Window Algorithm:** Tracks exact request timestamps for each user (or IP address) and counts requests within the last 60 seconds. Timestamps older than 60 seconds are automatically dropped, allowing for a smooth sliding window of request counts. This avoids the burst problem of fixed-window counters and ensures fair distribution of requests over time.
* **Thread Safety:** Uses `threading.Lock` to ensure that concurrent requests from multiple threads do not cause race conditions when updating the request.
* **Tiered Limits:** Anonymous users are limited to 5 requests per minute, while authenticated users can make up to 20 requests per minute. 
* **Memory Efficiency:** Keys with no active requests are automatically removed from the tracking dictionary to prevent memory bloat.

---

## Setup & Running Locally

### Prerequisites
* Python 3.10 or higher ([Download Python](https://www.python.org/downloads/)) - for running the application and tests.
* Git ([Download Git](https://git-scm.com/downloads)) - for cloning the repository.

### 1. Clone & Setup Virtual Environment

1. For **Windows**, run the following commands in the terminal (PowerShell, Command Prompt, or Git Bash):
```bash
git clone https://github.com/jatinpanigrahy/url-shortener-app.git
cd url-shortener-app

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```
* If windows blocks the venv activation due to execution policy, run the following command in PowerShell, then repeat the activation and installation steps:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

2. For **Linux or macOS**, run the following commands in the terminal:
```bash
git clone https://github.com/jatinpanigrahy/url-shortener-app.git
cd url-shortener-app

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python app.py
```
The server will automatically initialize `shortener.db` with all required tables and indexes, then start running on `http://127.0.0.1:5000` or `http://localhost:5000`.


### 3. Run Automated Tests
The application includes a comprehensive test suite in `test_app.py` created using Python's built-in `unittest` framework. To run the tests, execute the following command in the terminal:
```bash
python test_app.py
```

---

## API Documentation

### Public Endpoints

#### 1. System Health Check
`GET /health`
* **Status:** `200 OK`
* **Response:**
```json
{
  "service": "url-shortener-api",
  "status": "healthy"
}
```

#### 2. Shorten a URL
`POST /shorten` (or `POST /api/shorten`)
* **Headers:** `X-API-Key: <key>` *(optional)*
* **Body:**
```json
{
  "url": "https://www.python.org",
  "custom_alias": "py-home",
  "ttl_seconds": 86400
}
```
* **Status:** `201 Created`
* **Response:**
```json
{
  "short_code": "py-home",
  "short_url": "http://127.0.0.1:5000/py-home",
  "original_url": "https://www.python.org",
  "user_id": 1,
  "created_at": "2026-09-06 01:45:00",
  "expires_at": "2026-09-07T01:45:00+00:00"
}
```
* **Error Codes:** `400 Bad Request` (invalid URL/TTL), `409 Conflict` (alias taken), `429 Too Many Requests` (rate limited).

#### 3. Redirect to Original URL
`GET /<short_code>`
* **Status:** `302 Found` with `Location` header pointing to destination.
* **Error Codes:** `404 Not Found` (code does not exist), `410 Gone` (link has expired).

#### 4. URL Click Statistics
`GET /stats/<short_code>`
* **Status:** `200 OK`
* **Response:**
```json
{
  "short_code": "py-home",
  "original_url": "https://www.python.org",
  "user_id": 1,
  "click_count": 14,
  "created_at": "2026-09-06 01:45:00",
  "expires_at": "2026-09-07T01:45:00+00:00"
}
```

#### 5. Platform Analytics Dashboard
`GET /analytics`
* **Status:** `200 OK`
* **Response:**
```json
{
  "total_links": 25,
  "total_clicks": 340,
  "total_users": 4,
  "active_links": 23,
  "expired_links": 2,
  "top_5_urls": [
    {
      "short_code": "py-home",
      "original_url": "https://www.python.org",
      "click_count": 140,
      "created_at": "2026-09-06 01:45:00",
      "expires_at": null
    }
  ]
}
```

---

### Authentication & User Endpoints

#### 6. Register Account
`POST /auth/register`
* **Body:**
```json
{
  "email": "user@example.com",
  "password": "mypassword123"
}
```
* **Status:** `201 Created`
* **Response:**
```json
{
  "message": "User registered successfully.",
  "user_id": 1,
  "email": "user@example.com",
  "api_key": "usr_9kL2mP7Q..."
}
```

#### 7. Login
`POST /auth/login`
* **Body:**
```json
{
  "email": "user@example.com",
  "password": "mypassword123"
}
```
* **Status:** `200 OK`
* **Response:**
```json
{
  "message": "Authentication successful.",
  "user_id": 1,
  "api_key": "usr_9kL2mP7Q..."
}
```

#### 8. User Profile
`GET /auth/me`
* **Headers:** `X-API-Key: <your_key>`
* **Status:** `200 OK`
* **Response:**
```json
{
  "user_id": 1,
  "email": "user@example.com",
  "created_at": "2026-09-06 01:45:00"
}
```

#### 9. View My Links
`GET /my-urls`
* **Headers:** `X-API-Key: <your_key>`
* **Status:** `200 OK`
* **Response:** Returns an array of links created by the authenticated account.

#### 10. Delete Link
`DELETE /<short_code>`
* **Headers:** `X-API-Key: <your_key>` or `X-API-Key: <admin_key>`
* **Status:** `200 OK`
* **Response:**
```json
{
  "message": "Short URL 'py-home' has been successfully deleted."
}
```
* **Error Codes:** `401 Unauthorized` (missing key), `403 Forbidden` (key does not own this link).

---

## Directory Structure

```text
url-shortener/
├── templates/
│   └── index.html      # Responsive dashboard UI
├── app.py              # Flask server and route endpoints
├── core.py             # Application logic for URL shortening, hashing, and collision
├── database.py         # SQLite database connection and query functions
├── encoder.py          # Base62 encoder and SHA-256 hasher
├── limiter.py          # Rate limiting logic using sliding window algorithm
├── validator.py        # Input sanitization and validation (URL, alias, TTL)
├── test_app.py         # Test suite for the application using unittest framework
├── requirements.txt    # Python dependencies
├── .gitignore          # Git exclusion list 
└── README.md           # Documentation
```