# rules.py
# Checks if a result is valid, turns a list of results into a ranked leaderboard,
# and builds the "latest results" ticker.

from datetime import datetime, timezone

MAX_NAME_LENGTH = 40
MAX_SCORE = 1000000000  # one billion, so a typo can't break the database
MAX_MATCH_ID_LENGTH = 64

# The ways the admin can choose to rank teams. "best" is the default.
MODE_LABELS = {
    "best": "best single match",
    "total": "total points",
    "average": "average per match",
}


def clean_name(name):
    """Removes extra spaces. '  Nova   Squad ' becomes 'Nova Squad'."""
    return " ".join(name.split())


def check_result(data):
    """Returns an error message, or None if the result is OK."""
    if type(data) != dict:
        return "Send a JSON object with a name and a score."

    name = data.get("name")
    score = data.get("score")

    if type(name) != str or clean_name(name) == "":
        return "name is required and must be text."
    if len(clean_name(name)) > MAX_NAME_LENGTH:
        return "name must be 40 characters or less."

    # type() has to be exactly int. This rejects 5.5, "5", and true/false.
    if type(score) != int:
        return "score is required and must be a whole number."
    if score > MAX_SCORE or score < -MAX_SCORE:
        return "score is too big."

    # match_id is optional. If it's there, it has to be text or a whole number.
    match_id = data.get("match_id")
    if match_id is not None:
        if type(match_id) != str and type(match_id) != int:
            return "match_id must be text or a whole number."
        if len(str(match_id).strip()) == 0 or len(str(match_id)) > MAX_MATCH_ID_LENGTH:
            return "match_id must be 1 to 64 characters."

    return None


def get_match_id(data):
    """The match_id as text, or None if the game didn't send one. 17 and "17" are the same match."""
    match_id = data.get("match_id")
    if match_id is None:
        return None
    return str(match_id).strip()


def get_standings(results, mode="best"):
    """Groups results by team and ranks the teams.
    mode is "best", "total" or "average" (see MODE_LABELS)."""
    if mode not in MODE_LABELS:
        mode = "best"

    teams = {}

    for result in results:
        # Lowercase so "NOVA" and "nova" count as the same team.
        key = result["name"].lower()

        if key not in teams:
            teams[key] = {"name": result["name"], "best": result["score"], "total": 0, "matches": 0}

        team = teams[key]
        team["total"] = team["total"] + result["score"]
        team["matches"] = team["matches"] + 1
        if result["score"] > team["best"]:
            team["best"] = result["score"]

    leaderboard = list(teams.values())
    for team in leaderboard:
        team["average"] = round(team["total"] / team["matches"], 1)
        # Show 300 instead of 300.0
        if team["average"] == int(team["average"]):
            team["average"] = int(team["average"])

    # Sort by whichever number the admin picked, biggest first.
    def sort_key(team):
        return team[mode]

    leaderboard.sort(key=sort_key, reverse=True)

    # Teams with the same number share a rank, so ranks go 1, 2, 2, 4.
    for i in range(len(leaderboard)):
        if i > 0 and leaderboard[i][mode] == leaderboard[i - 1][mode]:
            leaderboard[i]["rank"] = leaderboard[i - 1]["rank"]
        else:
            leaderboard[i]["rank"] = i + 1

    return leaderboard


def seconds_since(created_at, now):
    """How many seconds ago a result came in. created_at looks like '2026-11-14 15:04:05'."""
    then = datetime.strptime(str(created_at)[:19], "%Y-%m-%d %H:%M:%S")
    return int((now - then).total_seconds())


def time_ago(seconds):
    """Turns 125 into '2 min ago'."""
    if seconds < 10:
        return "just now"
    if seconds < 60:
        return str(seconds) + " sec ago"
    if seconds < 3600:
        return str(seconds // 60) + " min ago"
    return str(seconds // 3600) + " hr ago"


def recent_results(results, count, now=None):
    """The newest results first, for the ticker. Results must be in the order they came in."""
    if now is None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

    recent = []
    i = len(results) - 1
    while i >= 0 and len(recent) < count:
        result = results[i]
        seconds = seconds_since(result["created_at"], now)
        recent.append({
            "name": result["name"],
            "score": result["score"],
            "ago": time_ago(seconds),
            "new": seconds < 60,
        })
        i = i - 1

    return recent


def also_tied(teams):
    """Only 3 teams fit on the podium. Returns the names of any other teams
    that tied for a podium spot (rank 3 or better), so we can list them too."""
    names = []
    for i in range(3, len(teams)):
        if teams[i]["rank"] <= 3:
            names.append(teams[i]["name"])
    return names


def find_team(teams, name):
    """Finds a team in the standings by name (capital letters don't matter). None if not found."""
    for team in teams:
        if team["name"].lower() == name.lower():
            return team
    return None


def chart_points(scores, width, height):
    """Works out where each score goes on the team page's line chart.
    Returns the list of points and how high the zero line is."""
    # The chart always includes 0, so you can see which scores were negative.
    low = 0
    high = 0
    for score in scores:
        if score < low:
            low = score
        if score > high:
            high = score
    if high == low:
        high = low + 1  # avoid dividing by zero

    points = []
    for i in range(len(scores)):
        if len(scores) == 1:
            x = width / 2
        else:
            x = i * width / (len(scores) - 1)
        # Bigger scores go higher, and SVG counts y from the top, so flip it.
        y = height - (scores[i] - low) / (high - low) * height
        points.append({"x": round(x, 1), "y": round(y, 1), "score": scores[i], "match": i + 1})

    zero_y = round(height - (0 - low) / (high - low) * height, 1)
    return points, zero_y
