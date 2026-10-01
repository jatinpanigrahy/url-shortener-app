import json
import os
import unittest
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from app import app
import database
import limiter

TEST_DB = "test_harness_patch.db"

class URLShortenerPatchTestCase(unittest.TestCase):
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

    def test_edit_url(self):
        # 1. Setup users
        owner = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "owner@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        owner_headers = {"X-API-Key": owner["api_key"]}

        other = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "other@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        other_headers = {"X-API-Key": other["api_key"]}

        # 2. Create link
        self.client.post(
            "/shorten",
            data=json.dumps({"url": "https://original.com", "custom_alias": "edit-link"}),
            headers=owner_headers,
            content_type="application/json",
        )

        # 3. Test Unauthorized (no api key)
        res_no_auth = self.client.patch("/edit-link", data=json.dumps({"original_url": "https://new.com"}), content_type="application/json")
        self.assertEqual(res_no_auth.status_code, 401)

        # 4. Test Forbidden (wrong user)
        res_forbidden = self.client.patch("/edit-link", data=json.dumps({"original_url": "https://new.com"}), headers=other_headers, content_type="application/json")
        self.assertEqual(res_forbidden.status_code, 403)

        # 5. Test invalid URLs
        res_invalid_ssrf = self.client.patch("/edit-link", data=json.dumps({"original_url": "http://127.0.0.1/admin"}), headers=owner_headers, content_type="application/json")
        self.assertEqual(res_invalid_ssrf.status_code, 400)

        res_invalid_js = self.client.patch("/edit-link", data=json.dumps({"original_url": "javascript:alert(1)"}), headers=owner_headers, content_type="application/json")
        self.assertEqual(res_invalid_js.status_code, 400)

        # 6. Test successful edit by owner
        res_success = self.client.patch("/edit-link", data=json.dumps({"original_url": "https://updated.com"}), headers=owner_headers, content_type="application/json")
        self.assertEqual(res_success.status_code, 200)

        data = res_success.get_json()
        expected_keys = ["short_code", "short_url", "original_url", "user_id", "created_at", "expires_at"]
        self.assertCountEqual(list(data.keys()), expected_keys)
        self.assertEqual(data["original_url"], "https://updated.com")
        self.assertEqual(data["short_code"], "edit-link")

        # Verify redirect goes to new url
        res_redirect = self.client.get("/edit-link")
        self.assertEqual(res_redirect.status_code, 302)
        self.assertEqual(res_redirect.headers["Location"], "https://updated.com")

        # 7. Test admin override
        admin = self.client.post(
            "/auth/register",
            data=json.dumps({"email": "admin2@test.com", "password": "password123"}),
            content_type="application/json",
        ).get_json()
        self._promote_to_admin(admin["user_id"])
        admin_headers = {"X-API-Key": admin["api_key"]}

        res_admin = self.client.patch("/edit-link", data=json.dumps({"original_url": "https://admin-updated.com"}), headers=admin_headers, content_type="application/json")
        self.assertEqual(res_admin.status_code, 200)

        res_redirect_admin = self.client.get("/edit-link")
        self.assertEqual(res_redirect_admin.headers["Location"], "https://admin-updated.com")

if __name__ == "__main__":
    unittest.main()
