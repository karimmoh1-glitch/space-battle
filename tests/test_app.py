# Tests for the website. Run them with:  python -m unittest discover tests

import os
import tempfile
import unittest
from datetime import datetime

import database

# Use a test database file and a test admin address, never the real ones.
test_folder = tempfile.mkdtemp()
database.DATABASE_URL = None
database.DATABASE_FILE = os.path.join(test_folder, "test.db")
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

    def test_rank_by_total_and_average(self):
        results = [{"name": "A", "score": 400}, {"name": "B", "score": 300},
                   {"name": "B", "score": 300}, {"name": "A", "score": -100}]
        by_total = rules.get_standings(results, "total")
        self.assertEqual(by_total[0]["name"], "B")
        self.assertEqual(by_total[0]["total"], 600)
        by_average = rules.get_standings(results, "average")
        self.assertEqual(by_average[0]["name"], "B")
        self.assertEqual(by_average[1]["average"], 150.0)

    def test_unknown_mode_uses_best(self):
        results = [{"name": "A", "score": 1}, {"name": "B", "score": 9}]
        self.assertEqual(rules.get_standings(results, "hacker")[0]["name"], "B")

    def test_recent_results_newest_first(self):
        now = datetime(2026, 11, 14, 12, 0, 0)
        results = [{"name": "A", "score": 1, "created_at": "2026-11-14 11:00:00"},
                   {"name": "B", "score": 2, "created_at": "2026-11-14 11:58:00"},
                   {"name": "C", "score": 3, "created_at": "2026-11-14 11:59:55"}]
        recent = rules.recent_results(results, 2, now)
        self.assertEqual([r["name"] for r in recent], ["C", "B"])
        self.assertEqual(recent[0]["ago"], "just now")
        self.assertTrue(recent[0]["new"])
        self.assertEqual(recent[1]["ago"], "2 min ago")
        self.assertFalse(recent[1]["new"])

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
        database.create_tables()
        database.save_setting("mode", "best")
        database.save_setting("locked", "no")
        database.save_setting("announcement", "")
        database.delete_all()
        self.client = app.app.test_client()

    def post(self, body):
        return self.client.post("/api/results", json=body)

    def test_pages_load(self):
        for page in ["/", "/display", "/rules", "/api-guide", "/about", "/ops/secret"]:
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

    def test_wrong_admin_path_cant_reset(self):
        self.post({"name": "Nova", "score": 5})
        self.assertEqual(self.client.post("/ops/wrong/reset", data={"confirm": "RESET"}).status_code, 404)
        self.assertEqual(len(database.all_results()), 1)

    def test_admin_add_edit_delete(self):
        self.client.post("/ops/secret/add", data={"name": "Nova", "score": "10"})
        result_id = database.all_results()[0]["id"]

        self.client.post(f"/ops/secret/edit/{result_id}", data={"name": "Nova", "score": "20"})
        self.assertEqual(database.get_result(result_id)["score"], 20)

        self.client.post(f"/ops/secret/delete/{result_id}")
        self.assertEqual(database.all_results(), [])

    def test_admin_rejects_bad_score(self):
        self.client.post("/ops/secret/add", data={"name": "Nova", "score": "ten"})
        self.assertEqual(database.all_results(), [])

    def test_reset_needs_the_word_reset(self):
        self.post({"name": "Nova", "score": 5})
        self.client.post("/ops/secret/reset", data={"confirm": "yes"})
        self.assertEqual(len(database.all_results()), 1)
        self.client.post("/ops/secret/reset", data={"confirm": "RESET"})
        self.assertEqual(database.all_results(), [])

    def test_live_json(self):
        self.post({"name": "Nova", "score": 5})
        data = self.client.get("/api/live").get_json()
        self.assertEqual(data["teams"][0]["name"], "Nova")
        self.assertEqual(data["recent"][0]["score"], 5)
        self.assertEqual(data["match_count"], 1)
        self.assertEqual(data["mode"], "best")
        self.assertFalse(data["locked"])

    def test_lock_stops_the_api(self):
        self.client.post("/ops/secret/lock", data={"locked": "yes"})
        response = self.post({"name": "Nova", "score": 5})
        self.assertEqual(response.status_code, 423)
        self.assertEqual(database.all_results(), [])
        self.assertIn("Final results", self.client.get("/").get_data(as_text=True))

        # Staff can still add scores by hand while it's locked.
        self.client.post("/ops/secret/add", data={"name": "Nova", "score": "10"})
        self.assertEqual(len(database.all_results()), 1)

        self.client.post("/ops/secret/lock", data={"locked": "no"})
        self.assertEqual(self.post({"name": "Nova", "score": 5}).status_code, 201)

    def test_change_ranking_mode(self):
        self.post({"name": "A", "score": 400})
        self.post({"name": "B", "score": 300})
        self.post({"name": "B", "score": 300})
        self.client.post("/ops/secret/mode", data={"mode": "total"})
        self.assertEqual(self.client.get("/api/leaderboard").get_json()[0]["name"], "B")
        self.client.post("/ops/secret/mode", data={"mode": "nonsense"})
        self.assertEqual(database.get_settings()["mode"], "total")

    def test_undo_delete(self):
        self.post({"name": "Nova", "score": 77})
        result_id = database.all_results()[0]["id"]
        self.client.post(f"/ops/secret/delete/{result_id}")
        self.assertEqual(database.all_results(), [])
        self.assertEqual(database.trash_count(), 1)

        self.client.post("/ops/secret/undo")
        self.assertEqual(database.all_results()[0]["score"], 77)
        self.assertEqual(database.trash_count(), 0)

        # Undo with an empty trash does nothing.
        self.client.post("/ops/secret/undo")
        self.assertEqual(len(database.all_results()), 1)

    def test_merge_team_names(self):
        self.post({"name": "nova", "score": 1})
        self.post({"name": "Nova Squad", "score": 2})
        self.client.post("/ops/secret/merge", data={"old_name": "NOVA", "new_name": " Nova  Squad "})
        teams = self.client.get("/api/leaderboard").get_json()
        self.assertEqual(len(teams), 1)
        self.assertEqual(teams[0]["matches"], 2)

    def test_announcement(self):
        self.client.post("/ops/secret/announce", data={"message": "Finals at 2pm"})
        self.assertEqual(self.client.get("/api/live").get_json()["announcement"], "Finals at 2pm")
        self.client.post("/ops/secret/announce", data={"message": "x" * 121})
        self.assertEqual(database.get_settings()["announcement"], "Finals at 2pm")

    def test_export_csv(self):
        self.post({"name": "=HACK()", "score": 5})
        response = self.client.get("/ops/secret/export.csv")
        text = response.get_data(as_text=True)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn("'=HACK()", text)
        self.assertEqual(self.client.get("/ops/wrong/export.csv").status_code, 404)

    def test_reset_empties_trash(self):
        self.post({"name": "Nova", "score": 5})
        self.client.post(f"/ops/secret/delete/{database.all_results()[0]['id']}")
        self.client.post("/ops/secret/reset", data={"confirm": "RESET"})
        self.assertEqual(database.trash_count(), 0)


if __name__ == "__main__":
    unittest.main()
