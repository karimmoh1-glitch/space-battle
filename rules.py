# rules.py
# The rules of the tournament: what counts as valid input and how teams are ranked.
# Nothing in this file touches the web or the database, so it is easy to test.

import math
import unicodedata
from datetime import datetime, timezone

MAX_NAME_LENGTH = 40
MAX_ID_LENGTH = 100
# The largest whole number JavaScript can store exactly (2 to the 53rd, minus 1).
MAX_SCORE = 9007199254740991


def clean_name(text):
    """Remove extra spaces, so '  Nova   Squad ' becomes 'Nova Squad'."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def check_name(name):
    """Returns (cleaned name, None) if valid, or (None, error message) if not."""
    if not isinstance(name, str):
        return None, "name must be text."
    name = clean_name(name)
    if len(name) < 1 or len(name) > MAX_NAME_LENGTH:
        return None, f"name must be 1 to {MAX_NAME_LENGTH} characters."
    if not name.isprintable():
        return None, "name contains characters that cannot be displayed."
    return name, None


def check_score(score):
    """Returns (score, None) if valid, or (None, error message) if not."""
    # We check type() because Python counts True and False as integers.
    if type(score) is not int:
        return None, "score must be a whole number."
    if score > MAX_SCORE or score < -MAX_SCORE:
        return None, "score is too large."
    return score, None


def check_submission(data):
    """Checks a full API request. Returns (cleaned dictionary, None) or (None, error)."""
    if not isinstance(data, dict):
        return None, "Send a JSON object with a name and a score."

    name, error = check_name(data.get("name"))
    if error:
        return None, error

    score, error = check_score(data.get("score"))
    if error:
        return None, error

    submission_id = data.get("submissionId")
    if submission_id is not None:
        if not isinstance(submission_id, str) or not 1 <= len(submission_id) <= MAX_ID_LENGTH:
            return None, f"submissionId must be text, 1 to {MAX_ID_LENGTH} characters."

    return {"name": name, "score": score, "submission_id": submission_id}, None


def build_teams(results):
    """Combines match results (oldest first) into one summary per team."""
    teams = {}
    for result in results:
        key = result["name"].lower()
        if key not in teams:
            teams[key] = {
                "key": key,
                "name": result["name"],
                "best": result["score"],
                "best_time": result["created_at"],
                "total": 0,
                "matches": 0,
                "last_match": result["created_at"],
            }

        team = teams[key]
        team["name"] = result["name"]  # the latest spelling wins
        team["total"] += result["score"]
        team["matches"] += 1
        team["last_match"] = result["created_at"]
        if result["score"] > team["best"]:
            team["best"] = result["score"]
            team["best_time"] = result["created_at"]

    return list(teams.values())


def sort_key(team):
    # Highest best score first. In a tie, whoever got there first. Then by name.
    return (-team["best"], team["best_time"], team["key"])


def rank_teams(teams):
    """Sorts teams and gives them ranks. Tied teams share a rank: 1, 1, 3."""
    teams = sorted(teams, key=sort_key)

    for i in range(len(teams)):
        team = teams[i]
        same_as_previous = i > 0 and teams[i - 1]["best"] == team["best"]
        same_as_next = i < len(teams) - 1 and teams[i + 1]["best"] == team["best"]

        if same_as_previous:
            team["rank"] = teams[i - 1]["rank"]
        else:
            team["rank"] = i + 1
        team["tied"] = same_as_previous or same_as_next

    return teams


def get_standings(results):
    return rank_teams(build_teams(results))


def rank_change(results):
    """How many places the latest match moved its team. Returns (team key, places)."""
    if len(results) < 2:
        return None, 0

    key = results[-1]["name"].lower()
    before = {team["key"]: team["rank"] for team in get_standings(results[:-1])}
    after = {team["key"]: team["rank"] for team in get_standings(results)}

    if key not in before:
        return None, 0
    return key, before[key] - after[key]


def get_stats(teams):
    """The numbers shown across the top of the board."""
    stats = {
        "teams": len(teams),
        "matches": sum(team["matches"] for team in teams),
        "top_score": None,
        "lead": None,
        "last_match": None,
    }
    if len(teams) > 0:
        stats["top_score"] = teams[0]["best"]
        stats["last_match"] = max(team["last_match"] for team in teams)
    if len(teams) > 1 and teams[0]["best"] != teams[1]["best"]:
        stats["lead"] = teams[0]["best"] - teams[1]["best"]
    return stats


def seconds_since(timestamp):
    then = datetime.fromisoformat(timestamp)
    return (datetime.now(timezone.utc) - then).total_seconds()


def time_ago(timestamp):
    """Turns a timestamp into text like '12s ago'."""
    seconds = max(0, int(seconds_since(timestamp)))
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    return f"{seconds // 3600}h ago"


def orbit_map(teams, limit=16):
    """Places the top teams around a star. A better rank means a smaller orbit."""
    center = 200
    inner_orbit = 48
    outer_orbit = 172

    shown = teams[:limit]
    if len(shown) == 0:
        return []
    last_rank = shown[-1]["rank"]

    ships = []
    for i in range(len(shown)):
        team = shown[i]

        fraction = 0
        if last_rank > 1:
            fraction = (team["rank"] - 1) / (last_rank - 1)
        radius = inner_orbit + fraction * (outer_orbit - inner_orbit)

        # Turning 2.4 radians per team spreads the ships evenly around the star.
        angle = -0.9 + i * 2.4
        x = center + math.cos(angle) * radius
        y = center + math.sin(angle) * radius

        name = team["name"]
        if len(name) > 16:
            name = name[:15] + "..."

        ships.append({
            "x": round(x, 1),
            "y": round(y, 1),
            "name": name,
            "top_three": i < 3,
            "label_left": x < center,
        })
    return ships
