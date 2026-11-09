# Tests the real web routes using a temporary database file.

import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import app as server
import database


class AppTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        database.use_file(os.path.join(self.folder.name, "test.db"))
        server.DEMO_MODE = False
        server.ADMIN_PATH = "secret-path"
        server.ADMIN_PASSWORD = "test-password"
        self.client = server.app.test_client()

    def tearDown(self):
        self.folder.cleanup()

    def post(self, body):
        text = body if isinstance(body, str) else json.dumps(body)
        return self.client.post("/api/results", data=text)

    def board(self):
        return self.client.get("/api/leaderboard").get_json()

    def login(self):
        self.client.post("/ops/secret-path/login", data={"password": "test-password"})


class TestApi(AppTest):
    def test_scores_stored_exactly(self):
        for score in [250, -100, 0, 9007199254740991]:
            response = self.post({"name": "Nova", "score": score})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.get_json()["result"]["score"], score)

    def test_invalid_requests(self):
        for body in [{"name": "N", "score": 1.5}, {"name": "N", "score": "5"}, {"name": "N"},
                     {"score": 5}, {"name": "  ", "score": 5}, {"name": "x" * 41, "score": 5},
                     [], "{not json", "", '{"name":"N","score":9007199254740993}']:
            response = self.post(body)
            self.assertEqual(response.status_code, 400, body)
            self.assertFalse(response.get_json()["ok"])

    def test_body_too_large(self):
        self.assertEqual(self.post({"name": "N", "score": 1, "x": "y" * 11000}).status_code, 413)

    def test_wrong_method(self):
        self.assertEqual(self.client.get("/api/results").status_code, 405)

    def test_repeats_without_id_are_separate_matches(self):
        self.post({"name": "Nova", "score": 5})
        self.post({"name": "Nova", "score": 5})
        self.assertEqual(self.board()["stats"]["matchCount"], 2)

    def test_repeated_submission_id(self):
        first = self.post({"name": "Nova", "score": 5, "submissionId": "m1"}).get_json()
        repeat = self.post({"name": "NOVA", "score": 5, "submissionId": "m1"})
        self.assertEqual(repeat.status_code, 200)
        self.assertTrue(repeat.get_json()["duplicate"])
        self.assertEqual(repeat.get_json()["result"]["id"], first["result"]["id"])
        self.assertEqual(self.board()["stats"]["matchCount"], 1)

    def test_conflicting_submission_id(self):
        self.post({"name": "Nova", "score": 5, "submissionId": "m1"})
        self.assertEqual(self.post({"name": "Nova", "score": 6, "submissionId": "m1"}).status_code, 409)

    def test_empty_leaderboard(self):
        board = self.board()
        self.assertEqual(board["teams"], [])
        self.assertIsNone(board["stats"]["topScore"])

    def test_ties(self):
        for name, score in [("A", 9), ("B", 9), ("C", 1)]:
            self.post({"name": name, "score": score})
        self.assertEqual([t["rank"] for t in self.board()["teams"]], [1, 1, 3])

    def test_huge_total_stays_exact(self):
        self.post({"name": "Big", "score": 9007199254740991})
        self.post({"name": "Big", "score": 9007199254740991})
        self.assertEqual(self.board()["teams"][0]["totalScore"], "18014398509481982")

    def test_concurrent_submissions(self):
        def send(number):
            server.app.test_client().post("/api/results", data=json.dumps({"name": "T", "score": number}))
        threads = [threading.Thread(target=send, args=(i,)) for i in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(self.board()["stats"]["matchCount"], 50)

    def test_cross_origin_allowed(self):
        response = self.post({"name": "N", "score": 1})
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")

    def test_database_failure(self):
        with patch("database.all_results", side_effect=sqlite3.OperationalError("secret detail")):
            response = self.client.get("/api/leaderboard")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("secret detail", response.get_data(as_text=True))
            self.assertEqual(self.client.get("/live/board").status_code, 503)

    def test_unexpected_error(self):
        server.app.config["PROPAGATE_EXCEPTIONS"] = False
        with patch("database.add_result", side_effect=TypeError("bug")):
            response = self.post({"name": "N", "score": 1})
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.get_json()["ok"])


class TestPages(AppTest):
    def test_pages_load(self):
        for path in ["/", "/display", "/rules", "/api-guide", "/about", "/live/board", "/live/display"]:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_board_with_data(self):
        self.post({"name": "<b>Nova</b>", "score": 500})
        html = self.client.get("/live/board").get_data(as_text=True)
        self.assertIn("500", html)
        self.assertNotIn("<b>Nova</b>", html)  # team names must not run as HTML

    def test_missing_page(self):
        self.assertEqual(self.client.get("/nope").status_code, 404)


class TestAdmin(AppTest):
    def rows(self):
        return database.all_results()

    def test_wrong_path_is_hidden(self):
        self.assertEqual(self.client.get("/ops/wrong").status_code, 404)

    def test_no_admin_when_not_configured(self):
        server.ADMIN_PASSWORD = None
        self.assertEqual(self.client.get("/ops/secret-path").status_code, 404)

    def test_wrong_password(self):
        self.client.post("/ops/secret-path/login", data={"password": "nope"})
        with self.client.session_transaction() as session:
            self.assertNotIn("admin", session)

    def test_actions_need_login(self):
        database.add_result("A", 1)
        base = "/ops/secret-path"
        for path in ["/add", "/edit/1", "/delete/1", "/reset"]:
            self.assertEqual(self.client.post(base + path, data={"confirm": "RESET TOURNAMENT"}).status_code, 403, path)
        self.assertEqual(self.client.get(base + "/backup").status_code, 403)
        self.assertEqual(len(self.rows()), 1)

    def test_add(self):
        self.login()
        self.client.post("/ops/secret-path/add", data={"name": "Nova", "score": "77"})
        self.assertEqual(self.rows()[0]["score"], 77)

    def test_add_rejects_bad_score(self):
        self.login()
        self.client.post("/ops/secret-path/add", data={"name": "Nova", "score": "1.5"})
        self.assertEqual(len(self.rows()), 0)

    def test_edit_keeps_first_original(self):
        self.login()
        database.add_result("Nova", 5)
        self.client.post("/ops/secret-path/edit/1", data={"name": "Nova", "score": "500"})
        self.client.post("/ops/secret-path/edit/1", data={"name": "Nova", "score": "600"})
        row = self.rows()[0]
        self.assertEqual((row["score"], row["original_score"]), (600, 5))

    def test_delete(self):
        self.login()
        database.add_result("Nova", 5)
        self.client.post("/ops/secret-path/delete/1")
        self.assertEqual(len(self.rows()), 0)

    def test_reset_needs_exact_phrase(self):
        self.login()
        database.add_result("Nova", 5)
        self.client.post("/ops/secret-path/reset", data={"confirm": "reset tournament"})
        self.assertEqual(len(self.rows()), 1)
        self.client.post("/ops/secret-path/reset", data={"confirm": "RESET TOURNAMENT"})
        self.assertEqual(len(self.rows()), 0)

    def test_search_and_filter(self):
        self.login()
        for i in range(5):
            database.add_result("Alpha", i)
        database.add_result("Beta", 9)
        database.update_result(6, "Beta", 10)
        self.assertEqual(database.search_results("alph", False, 1, 25)[1], 5)
        self.assertEqual(database.search_results("", True, 1, 25)[1], 1)
        self.assertEqual(database.search_results("%", False, 1, 25)[1], 0)
        self.assertEqual(self.client.get("/ops/secret-path?q=beta").status_code, 200)

    def test_backup(self):
        self.login()
        database.add_result("Nova", 5)
        response = self.client.get("/ops/secret-path/backup")
        self.assertEqual(json.loads(response.data)[0]["name"], "Nova")


if __name__ == "__main__":
    unittest.main()
