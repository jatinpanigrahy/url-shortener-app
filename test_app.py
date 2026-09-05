"""
Automated integration test harness for URL shortener. Executes end-to-end HTTP
contract tests using Flask's in-memory test client. No external dependencies are
used (runs via standard library unittest).
"""

import json
import os
import time
import unittest

import database
import limiter
from app import app

TEST_DB = "test_harness.db"


class URLShortenerTestCase(unittest.TestCase):
    def setUp(self):
        """Prepares an isolated database and clean rate-limit state before each test."""
        # 1. Unconditionally redirect all connection requests to TEST_DB
        self.original_db = database.DATABASE_NAME
        database.DATABASE_NAME = TEST_DB
        self.orig_conn = database.get_connection
        database.get_connection = lambda *args, **kwargs: self.orig_conn(TEST_DB)

        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except OSError:
                pass
        database.init_db(TEST_DB)

        # 2. Reset in-memory rate limiter logs
        with limiter._LOCK:
            limiter._REQUEST_LOG.clear()

        # 3. Create simulated HTTP test client
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        """Cleans up disk artifacts after each test completes."""
        database.get_connection = self.orig_conn
        database.DATABASE_NAME = self.original_db
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except OSError:
                pass

    # --- 1. Infrastructure & Basic Shortening Tests ---

    def test_01_health_check(self):
        """Verifies operational service health endpoint."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "healthy")

    def test_02_shorten_valid_url(self):
        """Verifies standard URL shortening write path."""
        payload = {"url": "https://www.python.org"}
        res = self.client.post(
            "/shorten",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertIn("short_code", data)
        self.assertEqual(len(data["short_code"]), 7)
        self.assertEqual(data["original_url"], "https://www.python.org")
        self.assertIsNone(data["expires_at"])

    def test_03_ssrf_and_malformed_url_defense(self):
        """Ensures loopback addresses and unsafe schemes are rejected with HTTP 400."""
        # SSRF loopback attempt
        res1 = self.client.post(
            "/shorten",
            data=json.dumps({"url": "http://127.0.0.1:8080/admin"}),
            content_type="application/json",
        )
        self.assertEqual(res1.status_code, 400)
        self.assertIn("prohibited", res1.get_json()["error"].lower())

        # Unsafe script scheme attempt
        res2 = self.client.post(
            "/shorten",
            data=json.dumps({"url": "javascript:alert(1)"}),
            content_type="application/json",
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn("only http and https", res2.get_json()["error"].lower())

    # --- 2. Custom Alias & Collision Tests ---

    def test_04_custom_alias_and_conflict(self):
        """Verifies custom alias assignment and duplicate collision rejection (409)."""
        payload = {"url": "https://example.com", "custom_alias": "custom-link"}
        res1 = self.client.post(
            "/shorten", data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(res1.status_code, 201)
        self.assertEqual(res1.get_json()["short_code"], "custom-link")

        # Second request with identical alias must trigger HTTP 409 Conflict
        res2 = self.client.post(
            "/shorten", data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(res2.status_code, 409)
        self.assertIn("already taken", res2.get_json()["error"].lower())

    # --- 3. Redirection, Click Tracking, and TTL Expiry Tests ---

    def test_05_redirect_and_atomic_metrics(self):
        """Verifies HTTP 302 Found redirect and atomic click_count increments."""
        # Create link
        self.client.post(
            "/shorten",
            data=json.dumps({"url": "https://github.com", "custom_alias": "gh-home"}),
            content_type="application/json",
        )

        # Baseline stats check (0 clicks)
        res_stats_before = self.client.get("/stats/gh-home")
        self.assertEqual(res_stats_before.get_json()["click_count"], 0)

        # Trigger redirect
        res_redirect = self.client.get("/gh-home")
        self.assertEqual(res_redirect.status_code, 302)
        self.assertEqual(res_redirect.headers["Location"], "https://github.com")

        # Stats check after redirect (1 click)
        res_stats_after = self.client.get("/stats/gh-home")
        self.assertEqual(res_stats_after.get_json()["click_count"], 1)

    def test_06_ttl_expiration_410_gone(self):
        """Verifies that expired links return HTTP 410 Gone."""
        # Create a link valid for 1 second
        self.client.post(
            "/shorten",
            data=json.dumps(
                {
                    "url": "https://news.ycombinator.com",
                    "custom_alias": "flash-news",
                    "ttl_seconds": 1,
                }
            ),
            content_type="application/json",
        )

        # Wait for expiration window to pass
        time.sleep(1.1)

        # Redirection must return HTTP 410
        res = self.client.get("/flash-news")
        self.assertEqual(res.status_code, 410)
        self.assertIn("expired", res.get_json()["error"].lower())

    # --- 4. Multi-Tenant Identity & Row-Level Authorization Tests ---

    def test_07_auth_registration_login_profile(self):
        """Verifies account provisioning, credential login, and profile introspection."""
        # Register User
        reg_payload = {"email": "tester@gdg.org", "password": "mypassword123"}
        res_reg = self.client.post(
            "/auth/register",
            data=json.dumps(reg_payload),
            content_type="application/json",
        )
        self.assertEqual(res_reg.status_code, 201)
        api_key = res_reg.get_json()["api_key"]
        self.assertTrue(api_key.startswith("usr_"))

        # Login
        res_login = self.client.post(
            "/auth/login",
            data=json.dumps(reg_payload),
            content_type="application/json",
        )
        self.assertEqual(res_login.status_code, 200)
        self.assertEqual(res_login.get_json()["api_key"], api_key)

        # Profile Introspection (/auth/me)
        res_me = self.client.get("/auth/me", headers={"X-API-Key": api_key})
        self.assertEqual(res_me.status_code, 200)
        self.assertEqual(res_me.get_json()["email"], "tester@gdg.org")

    def test_08_row_level_access_control_delete(self):
        """Verifies cross-tenant deletion rejection and authorized link deletion."""
        # 1. Register Alice and create her link
        res_alice = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "alice@gdg.org", "password": "password123"}),
            content_type="application/json",
        )
        alice_key = res_alice.get_json()["api_key"]

        self.client.post(
            "/shorten",
            data=json.dumps({"url": "https://alice.dev", "custom_alias": "alice-card"}),
            headers={"X-API-Key": alice_key},
            content_type="application/json",
        )

        # 2. Register Bob
        res_bob = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "bob@gdg.org", "password": "password123"}),
            content_type="application/json",
        )
        bob_key = res_bob.get_json()["api_key"]

        # 3. Bob attempts to delete Alice's link (Must return 403 Forbidden)
        res_bob_attack = self.client.delete(
            "/alice-card", headers={"X-API-Key": bob_key}
        )
        self.assertEqual(res_bob_attack.status_code, 403)

        # 4. Unauthenticated deletion attempt (Must return 401 Unauthorized)
        res_anon_attack = self.client.delete("/alice-card")
        self.assertEqual(res_anon_attack.status_code, 401)

        # 5. Alice deletes her own link (Must return 200 OK)
        res_alice_delete = self.client.delete(
            "/alice-card", headers={"X-API-Key": alice_key}
        )
        self.assertEqual(res_alice_delete.status_code, 200)

    # --- 5. Rate Limiter & Analytics Aggregator Tests ---

    def test_09_sliding_window_rate_limiter(self):
        """Verifies that exceeding the guest quota triggers an HTTP 429 Too Many Requests."""
        # Guest limit is 5 requests per 60 seconds
        for i in range(5):
            res = self.client.post(
                "/shorten",
                data=json.dumps({"url": f"https://example.com/page{i}"}),
                content_type="application/json",
            )
            self.assertEqual(res.status_code, 201)

        # The 6th request must be intercepted by the limiter
        res_blocked = self.client.post(
            "/shorten",
            data=json.dumps({"url": "https://example.com/page-blocked"}),
            content_type="application/json",
        )
        self.assertEqual(res_blocked.status_code, 429)
        self.assertIn("rate limit exceeded", res_blocked.get_json()["message"].lower())
        self.assertIn("Retry-After", res_blocked.headers)

    def test_10_analytics_aggregator(self):
        """Verifies the GET /analytics platform aggregation contract."""
        # Shorten link and simulate 2 clicks
        self.client.post(
            "/shorten",
            data=json.dumps(
                {"url": "https://trending-news.com", "custom_alias": "trend"}
            ),
            content_type="application/json",
        )
        self.client.get("/trend")
        self.client.get("/trend")

        # Query analytics
        res = self.client.get("/analytics")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertEqual(data["total_links"], 1)
        self.assertEqual(data["total_clicks"], 2)
        self.assertEqual(data["active_links"], 1)
        self.assertEqual(data["expired_links"], 0)
        self.assertEqual(len(data["top_5_urls"]), 1)
        self.assertEqual(data["top_5_urls"][0]["short_code"], "trend")


if __name__ == "__main__":
    unittest.main(verbosity=2)
