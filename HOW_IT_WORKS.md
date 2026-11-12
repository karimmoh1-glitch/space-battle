# How It Works

```
Match system  --POST /api/results-->  app.py  --> rules.py checks it --> database.py saves it
Browser       --GET /-->              app.py  --> rules.py ranks the teams --> index.html
```

## Saving a score

`add_result()` in `app.py`:

1. Reads the JSON.
2. Asks `rules.check_result()` if it's OK. If not, sends back `400` and the error.
3. Saves it with `database.add_result()`.
4. Sends back `201`.

## Ranking

`get_standings()` in `rules.py` loops over every result and builds a dictionary with one
entry per team (using the lowercase name, so "NOVA" and "Nova" are the same team). Then it
sorts the teams by best score. In the last loop, if a team has the same best score as the
team before it, it gets the same rank. That's how ranks go 1, 2, 2, 4.

Totals are never saved. They're added up every time the page loads. So if two scores
arrive at the same moment, they're just two new rows, and neither one can overwrite the other.

## The database

`database.py` has all the SQL. The `?` marks are blanks the database fills in safely, so
nobody can sneak SQL in through a team name.

On my computer it uses SQLite, which is one file. Vercel erases files, so the live site uses
Postgres. The SQL is the same except Postgres wants `%s` instead of `?`, so `run()` swaps them.

## Live updates

`index.html` has `<meta http-equiv="refresh" content="5">`, which makes the browser reload
the page every 5 seconds.

## Admin page

The address is secret (`ADMIN_PATH`), but a secret address isn't real security. The password
is. When you log in, Flask remembers it in `session`, which is a signed cookie. Every admin
route checks `logged_in()` first. Delete and reset ask "are you sure?", and reset only works
if you type RESET.

## Templates

Templates are HTML with `{% for %}` loops and `{{ blanks }}` that Flask fills in. Every
page starts with `{% extends "base.html" %}`, which has the menu and Pico CSS. Flask
escapes team names, so a team called `<script>` shows up as text and doesn't run.

## Practice ideas

1. Rank teams by total score instead of best score. Which tests break?
2. Add a page that shows one team's match history.
3. Show the time of each team's last match on the leaderboard.
