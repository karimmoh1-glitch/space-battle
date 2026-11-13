# 🚀 Space Battle Leaderboard

A live leaderboard for the Space Battle tournament, made for the Redmond High School TSA Webmaster qualifier
by Karim Mohamed and Dmitriy Bondar.
Match results come in through an API, the leaderboard updates itself every 5 seconds without
reloading, there's a big-screen mode for the projector, and a hidden admin page gives staff
the tools they need on game day.

**Live site:** https://space-battle-teal.vercel.app

## Built with

- **Python** and **Flask** for the server
- **HTML** with **Pico CSS** (amber theme) for the pages, plus our own `static/css/space.css`
- A little **JavaScript** (`static/js/live.js`) for live updates
- **SQLite** on my computer, **Postgres** on the live site

## Run it on your computer

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://localhost:8000.

To turn on the admin page, set these before `python app.py`:

```bash
export ADMIN_PATH="pick-a-long-secret-word"
export SECRET_KEY="any-random-text"
```

The admin page is then at `http://localhost:8000/ops/pick-a-long-secret-word`. The challenge
asks for security through obscurity, so there's no login: the secret address is the only
lock. Make it long and random, and only give it to staff.

## Pages

| Page | What it does |
|---|---|
| `/` | Leaderboard (podium, standings, latest results) |
| `/display` | Big screen for the projector |
| `/team/<name>` | One team's stats, score chart and every match |
| `/rules` | How ranking works |
| `/api-guide` | How to send results |
| `/about` | Team and credits |
| `/ops/<ADMIN_PATH>` | Admin page (see below) |

## Admin tools

- Add, edit and delete results (deletes can be undone)
- Merge or rename a team's results
- Switch the ranking: best single match, total points, or average per match
- Post an announcement on the leaderboard and big screen
- Lock the API for final results
- Download every result as a CSV file
- Reset the tournament (you have to type RESET)

## API

```bash
curl -X POST https://space-battle-teal.vercel.app/api/results \
  -H "Content-Type: application/json" \
  -d '{"name": "Nova Squad", "score": 250, "match_id": "round2-match7"}'
```

- `name`: text, 1 to 40 characters
- `score`: whole number, can be negative
- `match_id` (optional): if the same one is sent twice, it only counts once and the API returns `200` with `"duplicate": true`
- Returns `201` if saved, `400` with an `error` message if not, and `423` if staff locked the results

`GET /api/leaderboard` returns the teams as JSON. `GET /api/live` returns everything the
leaderboard page shows.

## Files

| File | What it does |
|---|---|
| `app.py` | The web pages, the API, and the admin page |
| `rules.py` | Checks results and ranks the teams |
| `database.py` | All the SQL |
| `templates/team.html` | A team's page with an SVG line chart |
| `templates/` | The HTML pages (`templates/parts/` has pieces used by more than one page) |
| `static/css/space.css` | Our colors, podium, starfield and big-screen styles |
| `static/js/live.js` | Updates the leaderboard every 5 seconds |
| `static/img/logo.svg` | The logo |
| `tests/` | Tests |

Read [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for more.

## Tests

```bash
python -m unittest discover tests
```

To test the live site (this adds test teams, so reset the tournament after):

```bash
python tests/live_check.py https://space-battle-teal.vercel.app
```

## Hosting

The live site runs on Vercel with a free Neon Postgres database. Vercel erases files, so
SQLite can't be used there. When the `DATABASE_URL` setting exists, `database.py` uses
Postgres instead.

To put changes online:

```bash
npx vercel deploy --prod
```

`ADMIN_PATH`, `SECRET_KEY` and `DATABASE_URL` are saved in the Vercel
project settings, not in the code.

## Before submitting

- Check the competition's rules on AI use
