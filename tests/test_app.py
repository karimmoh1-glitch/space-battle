# Tests for the website. Run them with:  python -m unittest discover tests

import os
import tempfile
import unittest

import database

# Use a test database file and the test secrets, never the real ones.
test_folder = tempfile.mkdtemp()
database.DATABASE_URL = None
database.DATABASE_FILE = os.path.join(test_folder, "test.db")
os.environ["ADMIN_PASSWORD"] = "test-password"
os.environ["ADMIN_PATH"] = "secret"

import app  # noqa: E402  (has to come after the setup above)
import rules  # noqa: E402


class RulesTests(unittest.TestCase):

    def test_good_result(self):
        self.assertIsNone(rules.check_result({"name": "Nova", "score": -20}))

    def test_bad_results(self):
        bad = [None, [], {"name": "Nova"}, {"score": 5}, {"name": "  ", "score": 5},
               {"name": "x" * 41, "score": 5}, {"name": "Nova", "score": 5.5},
               {"name": "Nova", "score": "5"}, {"name": "Nova", "score": True},
               {"name": 7, "score": 5}, {"name": "Nova", "score": 1000000001}]
        for data in bad:
            self.assertIsNotNone(rules.check_result(data), data)

    def test_clean_name(self):
        self.assertEqual(rules.clean_name("  Nova   Squad "), "Nova Squad")

    def test_ranked_by_best_score(self):
        results = [{"name": "A", "score": 100}, {"name": "B", "score": 300},
                   {"name": "A", "score": 400}, {"name": "A", "score": -50}]
        teams = rules.get_standings(results)
        self.assertEqual(teams[0]["name"], "A")
        self.assertEqual(teams[0]["best"], 400)
        self.assertEqual(teams[0]["total"], 450)
        self.assertEqual(teams[0]["matches"], 3)

    def test_ties_share_a_rank(self):
        results = [{"name": "A", "score": 410}, {"name": "B", "score": 410},
                   {"name": "C", "score": 500}, {"name": "D", "score": 100}]
        ranks = [team["rank"] for team in rules.get_standings(results)]
        self.assertEqual(ranks, [1, 2, 2, 4])

    def test_capitals_are_same_team(self):
        results = [{"name": "Nova", "score": 1}, {"name": "NOVA", "score": 2}]
        self.assertEqual(len(rules.get_standings(results)), 1)


class WebsiteTests(unittest.TestCase):

    def setUp(self):
        database.create_table()
        database.delete_all()
        self.client = app.app.test_client()

    def post(self, body):
        return self.client.post("/api/results", json=body)

    def login(self):
        self.client.post("/ops/secret", data={"password": "test-password"})

    def test_pages_load(self):
        for page in ["/", "/rules", "/api-guide", "/about"]:
            self.assertEqual(self.client.get(page).status_code, 200, page)

    def test_api_saves_result(self):
        response = self.post({"name": "  Nova  ", "score": 250})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(database.all_results()[0]["name"], "Nova")

    def test_api_rejects_bad_result(self):
        response = self.post({"name": "Nova", "score": "lots"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(database.all_results(), [])

    def test_api_rejects_broken_json(self):
        response = self.client.post("/api/results", data="{oops")
        self.assertEqual(response.status_code, 400)

    def test_leaderboard_json(self):
        self.post({"name": "Nova", "score": 5})
        teams = self.client.get("/api/leaderboard").get_json()
        self.assertEqual(teams[0]["name"], "Nova")

    def test_team_names_are_not_run_as_html(self):
        self.post({"name": "<script>bad</script>", "score": 5})
        page = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("<script>bad", page)

    def test_wrong_admin_path_is_404(self):
        self.assertEqual(self.client.get("/ops/wrong").status_code, 404)

    def test_wrong_password(self):
        self.client.post("/ops/secret", data={"password": "nope"})
        self.assertEqual(self.client.post("/ops/secret/reset", data={"confirm": "RESET"}).status_code, 403)

    def test_admin_add_edit_delete(self):
        self.login()
        self.client.post("/ops/secret/add", data={"name": "Nova", "score": "10"})
        result_id = database.all_results()[0]["id"]

        self.client.post(f"/ops/secret/edit/{result_id}", data={"name": "Nova", "score": "20"})
        self.assertEqual(database.get_result(result_id)["score"], 20)

        self.client.post(f"/ops/secret/delete/{result_id}")
        self.assertEqual(database.all_results(), [])

    def test_admin_rejects_bad_score(self):
        self.login()
        self.client.post("/ops/secret/add", data={"name": "Nova", "score": "ten"})
        self.assertEqual(database.all_results(), [])

    def test_reset_needs_the_word_reset(self):
        self.login()
        self.post({"name": "Nova", "score": 5})
        self.client.post("/ops/secret/reset", data={"confirm": "yes"})
        self.assertEqual(len(database.all_results()), 1)
        self.client.post("/ops/secret/reset", data={"confirm": "RESET"})
        self.assertEqual(database.all_results(), [])


if __name__ == "__main__":
    unittest.main()
