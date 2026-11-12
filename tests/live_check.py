# Tests a running website over the internet, including 50 requests at the same time.
# Start the server first, then run:  python tests/live_check.py http://localhost:8000
# It adds test teams, so reset the tournament from the admin page afterward.

import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

if len(sys.argv) > 1:
    url = sys.argv[1]
else:
    url = "http://localhost:8000"

test_name = "test-" + str(int(time.time()))
passed = 0
failed = 0


def check(label, ok):
    global passed, failed
    if ok:
        passed = passed + 1
        print("PASS", label)
    else:
        failed = failed + 1
        print("FAIL", label)


def post(body):
    """Sends a result to the API. Returns (status code, answer)."""
    if type(body) == bytes:
        data = body
    else:
        data = json.dumps(body).encode()
    request = urllib.request.Request(url + "/api/results", data=data,
                                     headers={"Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(request, timeout=30)
        return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def find_team(name):
    response = urllib.request.urlopen(url + "/api/leaderboard", timeout=30)
    for team in json.loads(response.read()):
        if team["name"].lower() == name.lower():
            return team
    return None


# Good results are saved exactly
for score in [250, -100, 0, 1000000000]:
    status, answer = post({"name": test_name, "score": score})
    check(f"saves score {score}", status == 201 and answer["result"]["score"] == score)

# Bad results are turned away
bad = [{"name": "x", "score": 1.5}, {"name": "x", "score": "5"}, {"name": "x", "score": True},
       {"name": "x"}, {"score": 1}, {"name": "   ", "score": 1}, {"name": "x" * 41, "score": 1},
       {"name": "x", "score": 1000000001}, [], b"{oops"]
for body in bad:
    status, answer = post(body)
    check(f"rejects {str(body)[:40]}", status == 400 and "error" in answer)

# The leaderboard adds things up correctly
team = find_team(test_name)
check("best score is right", team["best"] == 1000000000)
check("match count is right", team["matches"] == 4)

# Capital letters don't make a new team
post({"name": test_name.upper(), "score": 5})
check("capitals count as the same team", find_team(test_name)["matches"] == 5)

# 50 results at the exact same time are all saved
crowd_name = test_name + "-crowd"
with ThreadPoolExecutor(max_workers=50) as pool:
    answers = list(pool.map(lambda i: post({"name": crowd_name, "score": i}), range(50)))
check("50 at once all return 201", all(answer[0] == 201 for answer in answers))
crowd = find_team(crowd_name)
check("50 at once all saved", crowd["matches"] == 50)
check("50 at once total is right", crowd["total"] == sum(range(50)))

print()
print(passed, "passed,", failed, "failed")
if failed > 0:
    sys.exit(1)
