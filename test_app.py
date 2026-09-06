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

        with limiter._LOCK:
            limiter._REQUEST_LOG.clear()

        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        database.get_connection = self.orig_conn
        database.DATABASE_NAME = self.original_db
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except OSError:
                pass

    def test_01_health_check(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "healthy")

    def test_02_shorten_valid_url(self):
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
        self.assertIsNotNone(data["expires_at"])

    def test_03_ssrf_and_malformed_url_defense(self):
        res1 = self.client.post(
            "/shorten",
            data=json.dumps({"url": "http://127.0.0.1:8080/admin"}),
            content_type="application/json",
        )
        self.assertEqual(res1.status_code, 400)
        self.assertIn("prohibited", res1.get_json()["error"].lower())

        res2 = self.client.post(
            "/shorten",
            data=json.dumps({"url": "javascript:alert(1)"}),
            content_type="application/json",
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn("only http and https", res2.get_json()["error"].lower())

    def test_04_custom_alias_and_conflict(self):
        payload = {"url": "https://example.com", "custom_alias": "custom-link"}
        res_anon = self.client.post(
            "/shorten", data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(res_anon.status_code, 403)

        user = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "alias@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        headers = {"X-API-Key": user["api_key"]}

        res1 = self.client.post(
            "/shorten",
            data=json.dumps(payload),
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(res1.status_code, 201)
        self.assertEqual(res1.get_json()["short_code"], "custom-link")

        res2 = self.client.post(
            "/shorten",
            data=json.dumps(payload),
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(res2.status_code, 409)
        self.assertIn("already taken", res2.get_json()["error"].lower())

        res_reserved = self.client.post(
            "/shorten",
            data=json.dumps(
                {"url": "https://example.com", "custom_alias": "analytics"}
            ),
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(res_reserved.status_code, 400)
        self.assertIn("reserved", res_reserved.get_json()["error"].lower())

    def test_05_redirect_and_atomic_metrics(self):
        user = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "metrics@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        headers = {"X-API-Key": user["api_key"]}

        self.client.post(
            "/shorten",
            data=json.dumps({"url": "https://github.com", "custom_alias": "gh-home"}),
            headers=headers,
            content_type="application/json",
        )

        res_stats_before = self.client.get("/stats/gh-home", headers=headers)
        self.assertEqual(res_stats_before.get_json()["click_count"], 0)

        res_redirect = self.client.get("/gh-home")
        self.assertEqual(res_redirect.status_code, 302)
        self.assertEqual(res_redirect.headers["Location"], "https://github.com")

        res_stats_after = self.client.get("/stats/gh-home", headers=headers)
        self.assertEqual(res_stats_after.get_json()["click_count"], 1)

    def test_06_ttl_expiration_410_gone(self):
        user = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "ttl@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        headers = {"X-API-Key": user["api_key"]}

        self.client.post(
            "/shorten",
            data=json.dumps(
                {
                    "url": "https://news.ycombinator.com",
                    "custom_alias": "flash-news",
                    "ttl_seconds": 1,
                }
            ),
            headers=headers,
            content_type="application/json",
        )

        time.sleep(1.1)

        res = self.client.get("/flash-news")
        self.assertEqual(res.status_code, 410)
        self.assertIn("expired", res.get_json()["error"].lower())

    def test_07_auth_registration_login_profile(self):
        reg_payload = {"email": "tester@gdg.org", "password": "mypassword123"}
        res_reg = self.client.post(
            "/auth/register",
            data=json.dumps(reg_payload),
            content_type="application/json",
        )
        self.assertEqual(res_reg.status_code, 201)
        api_key = res_reg.get_json()["api_key"]
        self.assertTrue(api_key.startswith("usr_"))

        res_login = self.client.post(
            "/auth/login",
            data=json.dumps(reg_payload),
            content_type="application/json",
        )
        self.assertEqual(res_login.status_code, 200)
        self.assertEqual(res_login.get_json()["api_key"], api_key)

        res_me = self.client.get("/auth/me", headers={"X-API-Key": api_key})
        self.assertEqual(res_me.status_code, 200)
        self.assertEqual(res_me.get_json()["email"], "tester@gdg.org")

    def test_08_row_level_access_control_delete(self):
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

        res_bob = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "bob@gdg.org", "password": "password123"}),
            content_type="application/json",
        )
        bob_key = res_bob.get_json()["api_key"]

        res_bob_attack = self.client.delete(
            "/alice-card", headers={"X-API-Key": bob_key}
        )
        self.assertEqual(res_bob_attack.status_code, 403)

        res_anon_attack = self.client.delete("/alice-card")
        self.assertEqual(res_anon_attack.status_code, 401)

        res_alice_delete = self.client.delete(
            "/alice-card", headers={"X-API-Key": alice_key}
        )
        self.assertEqual(res_alice_delete.status_code, 200)

    def test_09_sliding_window_rate_limiter(self):
        for i in range(5):
            res = self.client.post(
                "/shorten",
                data=json.dumps({"url": f"https://example.com/page{i}"}),
                content_type="application/json",
            )
            self.assertEqual(res.status_code, 201)

        res_blocked = self.client.post(
            "/shorten",
            data=json.dumps({"url": "https://example.com/page-blocked"}),
            content_type="application/json",
        )
        self.assertEqual(res_blocked.status_code, 429)
        self.assertIn("rate limit exceeded", res_blocked.get_json()["message"].lower())
        self.assertIn("Retry-After", res_blocked.headers)

    def test_10_analytics_aggregator(self):
        user = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "trend@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        headers = {"X-API-Key": user["api_key"]}

        self.client.post(
            "/shorten",
            data=json.dumps(
                {"url": "https://trending-news.com", "custom_alias": "trend"}
            ),
            headers=headers,
            content_type="application/json",
        )
        self.client.get("/trend")
        self.client.get("/trend")

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
