# rules.py
# Checks if a result is valid, and turns a list of results into a ranked leaderboard.

MAX_NAME_LENGTH = 40
MAX_SCORE = 1000000000  # one billion, so a typo can't break the database


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

    return None


def get_best(team):
    return team["best"]


def get_standings(results):
    """Groups results by team and ranks the teams by their best score."""
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
    leaderboard.sort(key=get_best, reverse=True)

    # Teams with the same best score share a rank, so ranks go 1, 1, 3.
    for i in range(len(leaderboard)):
        if i > 0 and leaderboard[i]["best"] == leaderboard[i - 1]["best"]:
            leaderboard[i]["rank"] = leaderboard[i - 1]["rank"]
        else:
            leaderboard[i]["rank"] = i + 1

    return leaderboard
