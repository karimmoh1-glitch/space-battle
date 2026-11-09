# Tests a running server over the real network, including many requests at once.
# Start the server first, then run:  python tests/live_check.py http://localhost:8000
# It creates test teams, so reset the tournament from the admin page afterward.

import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
prefix = "__test-" + str(int(time.time()))
passed = 0
failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print("PASS ", label)
    else:
        failed += 1
        print("FAIL ", label)


def send(path, body=None, method=None):
    """Sends one request. Returns (status code, JSON answer)."""
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    request = urllib.request.Request(base_url + path, data=data, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def post(body):
    return send("/api/results", body)


def team(name):
    return prefix + "-" + name


def find(name):
    teams = send("/api/leaderboard")[1]["teams"]
    return [t for t in teams if t["name"].lower() == team(name).lower()]


for score in [250, -100, 0, 999999, 9007199254740991]:
    status, answer = post({"name": team("scores"), "score": score})
    check(f"stores {score} exactly", status == 201 and answer["result"]["score"] == score)

bad_bodies = [{"name": "x", "score": 1.5}, {"name": "x", "score": "5"}, {"name": "x", "score": None},
              {"name": "x"}, {"score": 1}, {"name": "   ", "score": 1}, {"name": "x" * 41, "score": 1},
              {"name": 7, "score": 1}, [], b"{oops", b'{"name":"x","score":9007199254740993}']
for body in bad_bodies:
    status, answer = post(body)
    check(f"rejects {str(body)[:40]}", status == 400 and answer["ok"] is False)

check("large body gives 413", post({"name": "x", "score": 1, "pad": "y" * 11000})[0] == 413)
check("wrong method gives 405", send("/api/results", {}, "PUT")[0] == 405)

submission = prefix + "-A"
first = post({"name": team("dup"), "score": 40, "submissionId": submission})
repeat = post({"name": team("dup"), "score": 40, "submissionId": submission})
check("new submissionId gives 201", first[0] == 201)
check("repeat gives 200 and same id", repeat[0] == 200 and repeat[1]["result"]["id"] == first[1]["result"]["id"])
check("conflict gives 409", post({"name": team("dup"), "score": 41, "submissionId": submission})[0] == 409)
check("duplicates stored once", find("dup")[0]["matches"] == 1)

post({"name": team("Case"), "score": 10})
post({"name": team("CASE"), "score": 90})
post({"name": "  " + team("case") + "  ", "score": -3})
case = find("case")
check("capitalization makes one team", len(case) == 1 and case[0]["bestScore"] == 90 and case[0]["totalScore"] == "97")

with ThreadPoolExecutor(max_workers=50) as pool:
    answers = list(pool.map(post, [{"name": team("load"), "score": i} for i in range(50)]))
statuses = [answer[0] for answer in answers]
check("50 at once all return 201", statuses.count(201) == 50)
check("50 at once stored exactly 50", find("load")[0]["matches"] == 50)
check("50 at once total is correct", find("load")[0]["totalScore"] == "1225")

race_body = {"name": team("race"), "score": 5, "submissionId": prefix + "-race"}
with ThreadPoolExecutor(max_workers=25) as pool:
    answers = list(pool.map(post, [race_body] * 25))
statuses = [answer[0] for answer in answers]
check("same ID 25 at once: one 201, rest 200", statuses.count(201) == 1 and statuses.count(200) == 24)
check("same ID 25 at once stored once", find("race")[0]["matches"] == 1)

check("health is 200", send("/api/health")[0] == 200)

print(f"\n{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
