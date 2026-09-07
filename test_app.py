"""
Automated integration test harness for URL shortener.
Executes end-to-end HTTP contract tests using Flask's in-memory test client.
Tests authentication, row-level authorization, rate limiting, and administrative moderation.
"""

import json
import os
import time
import unittest

from app import ADMIN_API_KEY, app
import database
import limiter

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

    def _promote_to_admin(self, user_id: int):
        conn = database.get_connection()
        with conn:
            conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?;", (user_id,))
        conn.close()

    def _set_user_banned(self, user_id: int, banned: bool = True):
        conn = database.get_connection()
        with conn:
            conn.execute(
                "UPDATE users SET is_banned = ? WHERE id = ?;",
                (1 if banned else 0, user_id),
            )
        conn.close()

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

        for reserved in ["analytics", "admin", "health"]:
            res_reserved = self.client.post(
                "/shorten",
                data=json.dumps(
                    {"url": "https://example.com", "custom_alias": reserved}
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
        reg_data = res_reg.get_json()
        api_key = reg_data["api_key"]
        self.assertTrue(api_key.startswith("usr_"))
        self.assertFalse(reg_data["is_admin"])

        res_login = self.client.post(
            "/auth/login",
            data=json.dumps(reg_payload),
            content_type="application/json",
        )
        self.assertEqual(res_login.status_code, 200)
        login_data = res_login.get_json()
        self.assertEqual(login_data["api_key"], api_key)
        self.assertFalse(login_data["is_admin"])

        res_me = self.client.get("/auth/me", headers={"X-API-Key": api_key})
        self.assertEqual(res_me.status_code, 200)
        me_data = res_me.get_json()
        self.assertEqual(me_data["email"], "tester@gdg.org")
        self.assertFalse(me_data["is_admin"])

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

    def test_11_admin_route_protection(self):
        res_anon = self.client.get("/admin/users")
        self.assertEqual(res_anon.status_code, 401)

        reg = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "regular@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        user_headers = {"X-API-Key": reg["api_key"]}

        res_forbidden = self.client.get("/admin/users", headers=user_headers)
        self.assertEqual(res_forbidden.status_code, 403)
        self.assertIn(
            "administrator privileges", res_forbidden.get_json()["error"].lower()
        )

        res_master = self.client.get(
            "/admin/users", headers={"X-API-Key": ADMIN_API_KEY}
        )
        self.assertEqual(res_master.status_code, 200)

        self._promote_to_admin(reg["user_id"])
        res_admin = self.client.get("/admin/users", headers=user_headers)
        self.assertEqual(res_admin.status_code, 200)

    def test_12_admin_users_pagination_and_search(self):
        admin = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "admin@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        self._promote_to_admin(admin["user_id"])
        admin_headers = {"X-API-Key": admin["api_key"]}

        with limiter._LOCK:
            limiter._REQUEST_LOG.clear()

        self.client.post(
            "/auth/register",
            data=json.dumps({"email": "john.doe@test.com", "password": "password123"}),
            content_type="application/json",
        )
        self.client.post(
            "/auth/register",
            data=json.dumps(
                {"email": "sarah.connor@test.com", "password": "password123"}
            ),
            content_type="application/json",
        )

        res_p1 = self.client.get("/admin/users?limit=2&offset=0", headers=admin_headers)
        self.assertEqual(res_p1.status_code, 200)
        data_p1 = res_p1.get_json()
        self.assertEqual(len(data_p1["users"]), 2)
        self.assertEqual(data_p1["total"], 3)
        self.assertTrue(data_p1["has_more"])
        self.assertEqual(data_p1["next_offset"], 2)

        res_search = self.client.get("/admin/users?search=sarah", headers=admin_headers)
        self.assertEqual(res_search.status_code, 200)
        data_search = res_search.get_json()
        self.assertEqual(data_search["total"], 1)
        self.assertEqual(data_search["users"][0]["email"], "sarah.connor@test.com")

    def test_13_admin_user_inspector_detail(self):
        admin = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "super@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        self._promote_to_admin(admin["user_id"])
        admin_headers = {"X-API-Key": admin["api_key"]}

        with limiter._LOCK:
            limiter._REQUEST_LOG.clear()

        user = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "target@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()

        self.client.post(
            "/shorten",
            data=json.dumps({"url": "https://example.com/target-link"}),
            headers={"X-API-Key": user["api_key"]},
            content_type="application/json",
        )

        res_detail = self.client.get(
            f"/admin/users/{user['user_id']}", headers=admin_headers
        )
        self.assertEqual(res_detail.status_code, 200)
        data = res_detail.get_json()
        self.assertEqual(data["email"], "target@test.com")
        self.assertEqual(data["total_links"], 1)

        res_urls = self.client.get(
            f"/admin/urls?user_id={user['user_id']}", headers=admin_headers
        )
        self.assertEqual(res_urls.status_code, 200)
        self.assertEqual(len(res_urls.get_json()["urls"]), 1)

    def test_14_admin_toggle_ban_and_enforcement(self):
        admin = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "boss@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        self._promote_to_admin(admin["user_id"])
        admin_headers = {"X-API-Key": admin["api_key"]}

        with limiter._LOCK:
            limiter._REQUEST_LOG.clear()

        user = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "spammer@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        user_headers = {"X-API-Key": user["api_key"]}

        res_self_ban = self.client.post(
            f"/admin/users/{admin['user_id']}/toggle-ban", headers=admin_headers
        )
        self.assertEqual(res_self_ban.status_code, 400)
        self.assertIn("cannot ban your own", res_self_ban.get_json()["error"].lower())

        res_ban = self.client.post(
            f"/admin/users/{user['user_id']}/toggle-ban", headers=admin_headers
        )
        self.assertEqual(res_ban.status_code, 200)
        self.assertEqual(res_ban.get_json()["is_banned"], 1)

        with limiter._LOCK:
            limiter._REQUEST_LOG.clear()

        res_login = self.client.post(
            "/auth/login",
            data=json.dumps({"email": "spammer@test.com", "password": "password123"}),
            content_type="application/json",
        )
        self.assertEqual(res_login.status_code, 403)
        self.assertIn("suspended", res_login.get_json()["error"].lower())

        res_me = self.client.get("/auth/me", headers=user_headers)
        self.assertEqual(res_me.status_code, 403)

        res_shorten = self.client.post(
            "/shorten",
            data=json.dumps({"url": "https://spam.com"}),
            headers=user_headers,
            content_type="application/json",
        )
        self.assertEqual(res_shorten.status_code, 403)

        res_unban = self.client.post(
            f"/admin/users/{user['user_id']}/toggle-ban", headers=admin_headers
        )
        self.assertEqual(res_unban.status_code, 200)
        self.assertEqual(res_unban.get_json()["is_banned"], 0)

        res_me_ok = self.client.get("/auth/me", headers=user_headers)
        self.assertEqual(res_me_ok.status_code, 200)

    def test_15_admin_delete_user_cascade(self):
        admin = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "cleaner@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        self._promote_to_admin(admin["user_id"])
        admin_headers = {"X-API-Key": admin["api_key"]}

        with limiter._LOCK:
            limiter._REQUEST_LOG.clear()

        victim = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "victim@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()

        link = self.client.post(
            "/shorten",
            data=json.dumps({"url": "https://victim.org", "custom_alias": "vic-link"}),
            headers={"X-API-Key": victim["api_key"]},
            content_type="application/json",
        ).get_json()

        res_self_del = self.client.delete(
            f"/admin/users/{admin['user_id']}", headers=admin_headers
        )
        self.assertEqual(res_self_del.status_code, 400)

        res_del = self.client.delete(
            f"/admin/users/{victim['user_id']}", headers=admin_headers
        )
        self.assertEqual(res_del.status_code, 200)

        res_user_check = self.client.get(
            f"/admin/users/{victim['user_id']}", headers=admin_headers
        )
        self.assertEqual(res_user_check.status_code, 404)

        res_link_check = self.client.get("/vic-link")
        self.assertEqual(res_link_check.status_code, 404)

    def test_16_admin_delete_arbitrary_link(self):
        admin = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "moderator@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        self._promote_to_admin(admin["user_id"])

        with limiter._LOCK:
            limiter._REQUEST_LOG.clear()

        user = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "author@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()

        self.client.post(
            "/shorten",
            data=json.dumps(
                {"url": "https://bad-site.com", "custom_alias": "flagged-url"}
            ),
            headers={"X-API-Key": user["api_key"]},
            content_type="application/json",
        )

        res_delete = self.client.delete(
            "/flagged-url", headers={"X-API-Key": admin["api_key"]}
        )
        self.assertEqual(res_delete.status_code, 200)

        res_check = self.client.get("/flagged-url")
        self.assertEqual(res_check.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
