# Run all the tests with:  python -m unittest discover tests

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import rules


def team(key, best, best_time="2026-11-14T10:00:00", matches=1):
    return {"key": key, "name": key, "best": best, "best_time": best_time,
            "total": best, "matches": matches, "last_match": best_time}


def match(name, score, time="2026-11-14T10:00:00"):
    return {"name": name, "score": score, "created_at": time}


class TestValidation(unittest.TestCase):
    def accepted(self, score):
        return rules.check_submission({"name": "Nova", "score": score})[1] is None

    def test_good_scores(self):
        for score in [250, -100, 0, 999999, rules.MAX_SCORE, -rules.MAX_SCORE]:
            self.assertTrue(self.accepted(score), score)

    def test_bad_scores(self):
        for score in [1.5, "250", None, True, rules.MAX_SCORE + 1, -rules.MAX_SCORE - 1]:
            self.assertFalse(self.accepted(score), score)

    def test_missing_fields(self):
        self.assertIsNotNone(rules.check_submission({"name": "Nova"})[1])
        self.assertIsNotNone(rules.check_submission({"score": 5})[1])

    def test_body_must_be_an_object(self):
        for body in [None, [], "hello", 42]:
            self.assertIsNotNone(rules.check_submission(body)[1])

    def test_name_cleanup(self):
        self.assertEqual(rules.check_name("  Nova   Squad ")[0], "Nova Squad")
        self.assertEqual(rules.check_name("Nova\t\nSquad")[0], "Nova Squad")

    def test_bad_names(self):
        for name in ["", "    ", "x" * 41, 42, None, "No\x00va"]:
            self.assertIsNotNone(rules.check_name(name)[1], name)

    def test_longest_name_allowed(self):
        self.assertIsNone(rules.check_name("x" * 40)[1])

    def test_submission_id(self):
        self.assertEqual(rules.check_submission({"name": "N", "score": 1, "submissionId": "a"})[0]["submission_id"], "a")
        for bad in ["", 7, "x" * 101]:
            self.assertIsNotNone(rules.check_submission({"name": "N", "score": 1, "submissionId": bad})[1])


class TestRanking(unittest.TestCase):
    def ranks(self, teams):
        return [(t["key"], t["rank"], t["tied"]) for t in rules.rank_teams(teams)]

    def test_empty(self):
        self.assertEqual(rules.rank_teams([]), [])

    def test_highest_first(self):
        self.assertEqual(self.ranks([team("a", 10), team("b", 30)]),
                         [("b", 1, False), ("a", 2, False)])

    def test_ties_share_a_rank_and_skip(self):
        result = self.ranks([team("a", 50), team("b", 50), team("c", 20)])
        self.assertEqual([r[1] for r in result], [1, 1, 3])

    def test_tie_in_the_middle(self):
        self.assertEqual(self.ranks([team("a", 90), team("b", 50), team("c", 50), team("d", 10)]),
                         [("a", 1, False), ("b", 2, True), ("c", 2, True), ("d", 4, False)])

    def test_earlier_achiever_first(self):
        result = rules.rank_teams([team("late", 5, "2026-11-14T11:00:00"), team("early", 5, "2026-11-14T09:00:00")])
        self.assertEqual(result[0]["key"], "early")

    def test_negative_scores(self):
        self.assertEqual([r[0] for r in self.ranks([team("n", -5), team("z", 0), team("w", -50)])], ["z", "n", "w"])

    def test_multiple_results_same_team(self):
        teams = rules.get_standings([match("nova", 10), match("NOVA", 40), match("Nova", -5)])
        self.assertEqual(len(teams), 1)
        self.assertEqual((teams[0]["name"], teams[0]["best"], teams[0]["total"], teams[0]["matches"]), ("Nova", 40, 45, 3))

    def test_rank_change(self):
        results = [match("a", 50), match("b", 20), match("b", 90)]
        self.assertEqual(rules.rank_change(results), ("b", 1))

    def test_no_rank_change_for_new_team(self):
        self.assertEqual(rules.rank_change([match("a", 50), match("b", 90)]), (None, 0))


class TestStats(unittest.TestCase):
    def test_empty(self):
        stats = rules.get_stats([])
        self.assertEqual((stats["teams"], stats["top_score"], stats["lead"]), (0, None, None))

    def test_lead(self):
        self.assertEqual(rules.get_stats(rules.rank_teams([team("a", 90), team("b", 70)]))["lead"], 20)

    def test_no_lead_when_first_is_tied(self):
        self.assertIsNone(rules.get_stats(rules.rank_teams([team("a", 9), team("b", 9)]))["lead"])

    def test_orbit_map(self):
        self.assertEqual(rules.orbit_map([]), [])
        ships = rules.orbit_map(rules.rank_teams([team("a", 9), team("b", 5)]))
        self.assertEqual(len(ships), 2)
        self.assertTrue(ships[0]["top_three"])


if __name__ == "__main__":
    unittest.main()
