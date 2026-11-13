# How It Works

```
Match system  --POST /api/results-->  app.py  --> rules.py checks it --> database.py saves it
Browser       --GET /-->              app.py  --> rules.py ranks the teams --> index.html
live.js       --GET /api/live-->      app.py  --> same data as JSON, every 5 seconds
```

## Saving a score

`add_result()` in `app.py`:

1. Reads the JSON.
2. If staff locked the results, sends back `423` and stops.
3. Asks `rules.check_result()` if it's OK. If not, sends back `400` and the error.
4. Saves it with `database.add_result()`. If the game sent a `match_id` that's already saved,
   `ON CONFLICT DO NOTHING` skips the insert and we send back the old result with `200`.
5. Otherwise sends back `201`.

The database has a `UNIQUE` index on `match_id`, so even two copies of the same match arriving
at the exact same moment can't both be saved. Results without a `match_id` (NULL) are never
treated as duplicates.

## Ranking

`get_standings()` in `rules.py` loops over every result and builds a dictionary with one
entry per team (using the lowercase name, so "NOVA" and "Nova" are the same team). Then it
works out each team's average and sorts the teams by the number the admin picked (`mode` is
`"best"`, `"total"` or `"average"`). In the last loop, if a team has the same number as the
team before it, it gets the same rank. That's how ranks go 1, 2, 2, 4.

Totals are never saved. They're added up every time the page loads. So if two scores
arrive at the same moment, they're just two new rows, and neither one can overwrite the other.

## The database

`database.py` has all the SQL. The `?` marks are blanks the database fills in safely, so
nobody can sneak SQL in through a team name.

On my computer it uses SQLite, which is one file. Vercel erases files, so the live site uses
Postgres. The SQL is the same except Postgres wants `%s` instead of `?`, so `run()` swaps them.

## Live updates

The server builds the first version of the page. After that, `static/js/live.js` runs
`update()` every 5 seconds:

1. `fetch("/api/live")` gets the newest data as JSON.
2. `updateArrows()` compares each team's rank to the last update. If it went up, it gets a
   ▲ for 6 updates (30 seconds). It also notes which teams played a new match, so their row flashes.
3. `showPodium()`, `showStandings()` and `showRecent()` empty each part of the page and
   rebuild it with a `for` loop. They use `textContent`, never `innerHTML`, so a team name
   can't sneak code onto the page.
4. If the fetch fails, the page keeps the old scores and says "Connection lost, retrying".

If JavaScript is turned off, a `<noscript>` tag reloads the whole page every 10 seconds instead.

`/display` uses the same pieces (`templates/parts/`) with bigger text, no menu, and the
latest results scrolling across the bottom (a CSS animation in `space.css`).

## Team pages

`/team/<name>` finds the team with `rules.find_team()` and gets its results with
`database.team_results()`. The line chart is plain SVG. `rules.chart_points()` loops over the
scores and turns each one into an (x, y) spot: x spreads the matches evenly across 600 pixels,
and y is the score's spot between the lowest and highest score, flipped because SVG counts y
from the top. The chart always includes 0, so negative scores show below a dashed zero line.

## Ties on the podium

Only 3 cards fit on the podium. If more teams tie for a top-3 rank, `rules.also_tied()` lists
the extras and the page shows "Also tied for a podium spot" under the podium.

## Look and feel

Pico CSS does almost all the styling. We picked Pico's amber theme and changed a few of its
CSS variables in `space.css` to get the dark "deep space" colors. The stars are small
`radial-gradient` dots repeated across the background. The podium uses CSS grid, and
`order` moves 1st place into the middle.

## Admin page

The challenge asks for security through obscurity, so there's no login. Every admin route
starts with `check_admin_path()`, which shows "page not found" unless the address matches
the secret `ADMIN_PATH`. The page also tells search engines not to list it.

- **Delete and undo:** deleting moves the result to a `deleted_results` table instead of
  erasing it. Undo moves the newest one back. Both steps run in one transaction with
  `run_together()`, so a crash can't leave a result in both tables or in neither.
- **Settings:** the ranking mode, the lock and the announcement are rows in a `settings`
  table (`name`, `value`).
- **Merge:** one `UPDATE` renames every result for a team.
- **CSV:** Python's `csv` module writes every result. Names starting with `=` get a `'` in
  front so Excel doesn't run them as formulas.
- Delete and lock ask "are you sure?", and reset only works if you type RESET.

## Templates

Templates are HTML with `{% for %}` loops and `{{ blanks }}` that Flask fills in. Every
page starts with `{% extends "base.html" %}`, which has the menu and Pico CSS. Flask
escapes team names, so a team called `<script>` shows up as text and doesn't run.

## Practice ideas

1. Add a fourth ranking mode, like "most matches played".
2. Add a "best streak" number to the team page.
3. Let the admin pick how many teams the big screen shows.
