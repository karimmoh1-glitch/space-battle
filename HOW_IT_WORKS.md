# How It Works

## The big picture

```
Match system -> POST /api/results -> check the data -> save to SQLite
Browser, every 3 seconds -> /live/board -> Python rebuilds the HTML -> page updates
Coordinator -> /ops/secret -> password -> forms that change the database
```

The browser never talks to the database. Only Python does.

## Python files

**`rules.py`** has no web or database code, only functions. That makes it the best place to start.

- `check_submission` returns a pair: `(cleaned data, None)` if good, `(None, error message)` if bad.
- `build_teams` loops through every match and builds a dictionary with one entry per team.
- `rank_teams` sorts the teams, then walks the list. If a team has the same best score as the team before it, it copies that rank. Otherwise its rank is its position. That one `if` is what makes 1, 1, 3.

**`database.py`** holds all SQL. The `?` marks let the database insert values safely, so text someone types can never run as SQL.

It works with two databases. On your computer it uses SQLite, a single file. On Vercel, files are erased between requests, so the live site uses Postgres, a database server. If the `DATABASE_URL` setting exists, `connect()` opens Postgres; otherwise it opens the file. The two speak almost the same SQL. The `run` function swaps `?` for `%s`, the blank Postgres expects, and `search_results` picks `strpos` or `instr`.

**`app.py`** connects web addresses to functions. `@app.route("/rules")` means "when someone visits /rules, run the function below."

## How a score gets saved

Follow `submit_result` in `app.py`:

1. Read the JSON. If it is broken, answer 400.
2. Call `rules.check_submission`. If it fails, answer 400 with the reason.
3. Call `database.add_result`.
4. Answer 201.

## Why simultaneous requests are safe

Each match is its own row, and totals are calculated when the board is read. Because no total is ever saved, two requests can never overwrite each other's update.

`submission_id` is marked `UNIQUE`, so the database itself refuses a second copy, even if both arrive in the same instant. `add_result` catches that refusal and returns `None`.

## How the board updates by itself

1. `index.html` is mostly an empty box with `id="live-board"`.
2. `live.js` asks `/live/board` for the newest HTML and puts it in the box.
3. It waits 3 seconds and does it again.

Python and the Jinja template `_board.html` do the real work. JavaScript only moves the finished HTML onto the page. HTML, CSS, and Python cannot update an open page by themselves, so this is the one job JavaScript does here.

## Templates

Templates are HTML with `{% for %}` loops, `{% if %}` checks, and `{{ variable }}` blanks that Flask fills in. `base.html` holds what every page shares. Other pages start with `{% extends "base.html" %}` and fill in the content block. Filenames starting with `_` are pieces included in other pages.

Jinja automatically makes text safe, so a team named `<script>` shows as text and does not run.

## Orbit map

`orbit_map` in `rules.py` is trigonometry you already know. Each team gets a radius from its rank and an angle from its position. Then `x = center + cos(angle) * radius` and `y = center + sin(angle) * radius`.

## The admin panel

The address is hidden, but hiding is not security. The password check on the server is. After you log in, Flask remembers it in a signed cookie through `session`. Every admin function checks `is_logged_in()` first.

## Practice

Try each of these without looking at the answer first.

1. Change ranking to use each team's total instead of its best. Which tests fail, and why?
2. Add a "matches played" number to the projector view.
3. Add a new rule that rejects team names containing only numbers. Write a test first.
4. Add a page that shows one team's match history.
5. Write the `rank_teams` function again from memory, then run `tests/test_rules.py`.

## Questions to be able to answer

1. Why is the database key never sent to the browser?
2. What happens when two requests use the same `submissionId` at once?
3. How do two teams tied at 410 get ranks, and what rank comes next?
4. What does the hidden address protect, and what does the password protect?
5. Why does the live site need Postgres instead of the SQLite file?
