# SPACE BATTLE: Mission Control

A live tournament leaderboard with a public score API and a hidden coordinator panel, for the TSA@RHS Webmaster qualifier. Built with Python (Flask), SQLite, HTML, and CSS.

> **Authorship notice:** this code, design, and text were generated with AI assistance (Claude, by Anthropic). The competition requires key parts of an entry to be the team's original work, so check the organizers' AI rules before submitting it. See [CREDITS.md](CREDITS.md).

![Projector view](screenshots/projector.png)

## Run the demo

You need Python 3.10 or newer.

**Mac or Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py --demo
```

**Windows**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py --demo
```

Then open http://localhost:8000. The admin page is http://localhost:8000/ops/demo and the password is `demo`.

Demo mode uses made-up teams in a separate file (`demo.db`), adds new fake matches as the board runs, and shows an orange banner on every screen. It never touches real results.

## Pages

| Address | What it is |
|---|---|
| `/` | Live leaderboard |
| `/display` | Full-screen projector view |
| `/rules` | How scoring works |
| `/api-guide` | How to send results |
| `/about` | Team and citations |
| `/ops/<secret path>` | Hidden coordinator panel |

## The API

Send a match:

```bash
curl -X POST http://localhost:8000/api/results \
  -H "Content-Type: application/json" \
  -d '{"name": "Nova Squad", "score": 250}'
```

| Field | Required | Rules |
|---|---|---|
| `name` | Yes | Text, 1 to 40 characters |
| `score` | Yes | Signed whole number, no typical-range limit |
| `submissionId` | No | Your own match ID, so a retry is not counted twice |

| Status | Meaning |
|---|---|
| 201 | Saved |
| 200 | Repeat of a `submissionId`. Nothing added |
| 400 | Invalid request. The `error` field explains why |
| 405 | Wrong HTTP method |
| 409 | `submissionId` reused with a different name or score |
| 413 | Request over 10 KB |
| 503 | Database unavailable. Safe to retry |

`GET /api/leaderboard` returns the standings as JSON.

## Ranking

- A team's rank comes from its **highest single match score**.
- Tied teams **share a rank** (1, 1, 3). The team that reached the score first is listed first.
- Capitalization and extra spaces are ignored in team names.
- Without a `submissionId`, identical requests count as separate matches, because two matches can have the same score.

## Run for real

Set a password and a secret admin address, then start the app. Without these two, the admin page stays switched off.

```bash
export ADMIN_PASSWORD="choose-a-long-password"
export ADMIN_PATH="choose-a-secret-word"
export SECRET_KEY="any-long-random-text"
python app.py
```

Results are saved in `spacebattle.db`, which is deliberately not uploaded to GitHub.

## Admin panel

Go to `/ops/<ADMIN_PATH>` and enter the password. You can search, filter, add, correct, and delete results, download a backup, and reset the tournament. Reset requires typing `RESET TOURNAMENT`.

## Hosting

SQLite is a file on disk, so the host must keep files between requests. **Vercel and similar serverless hosts will not work.**

PythonAnywhere has a free plan that suits this. In short:

1. Make an account and upload the code, or `git clone` it in a Bash console.
2. Create a virtual environment and run `pip install -r requirements.txt`.
3. Add a Flask web app pointing at this folder.
4. In its WSGI file, set the three variables above with `os.environ[...]`, then `from app import app as application`.
5. Reload the app, then test it with `python tests/live_check.py https://yourname.pythonanywhere.com`. That script creates test teams, so reset the tournament afterward.

Check PythonAnywhere's current free-plan limits and expiry rules, and log in before the judging date so the site does not expire.

## Tests

```bash
python -m unittest discover tests
```

To test a running server, including 50 requests at the same moment:

```bash
python tests/live_check.py http://localhost:8000
```

## How the code is organized

| File | Job |
|---|---|
| `app.py` | Web addresses and what each one does |
| `rules.py` | Validation and ranking, as plain functions |
| `database.py` | Every SQL statement |
| `templates/` | The HTML pages |
| `static/style.css` | All of the design |
| `static/live.js` | Refreshes the board every 3 seconds |

Read [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for a walkthrough.

## Before submitting

- Replace `TEAM_MEMBERS` in `app.py` with real names
- Confirm the AI rules and any annual theme with the organizers
