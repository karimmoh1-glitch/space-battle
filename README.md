# 🚀 Space Battle Leaderboard

A live leaderboard for the Space Battle tournament, made for the TSA@RHS Webmaster qualifier.
Match results come in through an API, the leaderboard updates every 5 seconds, and a hidden
admin page lets staff fix mistakes.

**Live site:** https://space-battle-teal.vercel.app

## Built with

- **Python** and **Flask** for the server
- **HTML** with **Pico CSS** for the pages
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
export ADMIN_PASSWORD="pick-a-password"
export ADMIN_PATH="pick-a-secret-word"
export SECRET_KEY="any-random-text"
```

The admin page is then at `http://localhost:8000/ops/pick-a-secret-word`.

## Pages

| Page | What it does |
|---|---|
| `/` | Leaderboard |
| `/rules` | How ranking works |
| `/api-guide` | How to send results |
| `/about` | Team and credits |
| `/ops/<ADMIN_PATH>` | Admin page (add, edit, delete, reset) |

## API

```bash
curl -X POST https://space-battle-teal.vercel.app/api/results \
  -H "Content-Type: application/json" \
  -d '{"name": "Nova Squad", "score": 250}'
```

- `name`: text, 1 to 40 characters
- `score`: whole number, can be negative
- Returns `201` if saved, `400` with an `error` message if not

`GET /api/leaderboard` returns the teams as JSON.

## Files

| File | What it does |
|---|---|
| `app.py` | The web pages, the API, and the admin page |
| `rules.py` | Checks results and ranks the teams |
| `database.py` | All the SQL |
| `templates/` | The HTML pages |
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

`ADMIN_PASSWORD`, `ADMIN_PATH`, `SECRET_KEY` and `DATABASE_URL` are saved in the Vercel
project settings, not in the code.

## Before submitting

- Put your real names in `templates/about.html`
- Check the competition's rules on AI use
