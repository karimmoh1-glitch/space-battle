# Space Battle: Endpoint and Admin Panel Documentation

Redmond High School TSA, Webmaster qualifier. Team: Karim Mohamed and Dmitriy Bondar.

For the TSA@RHS Webmaster documentation form (due Thursday, Nov 12, end of day).

**Live site:** https://space-battle-teal.vercel.app
**Big screen (projector):** https://space-battle-teal.vercel.app/display
**Code:** https://github.com/karimmoh1-glitch/space-battle

## Sending a match result

```
POST https://space-battle-teal.vercel.app/api/results
Content-Type: application/json

{"name": "Nova Squad", "score": 250}
```

| Field | Rules |
|---|---|
| `name` | Required. Text, 1 to 40 characters. Extra spaces are removed, and capital letters don't matter ("NOVA SQUAD" and "Nova Squad" are the same team). |
| `score` | Required. A whole number, sent as a number, not text. Negative is fine. Limit ±1,000,000,000. |

Example:

```bash
curl -X POST https://space-battle-teal.vercel.app/api/results \
  -H "Content-Type: application/json" \
  -d '{"name": "Nova Squad", "score": 250}'
```

| Status | Meaning |
|---|---|
| `201` | Saved. The response is `{"ok": true, "result": {...}}`. |
| `400` | Bad request. The response is `{"ok": false, "error": "..."}`, and the error says what's wrong. |
| `413` | The body is bigger than 10 KB. |
| `423` | Staff locked the results (tournament over). Nothing was saved. |
| `503` | The database is down. Send it again. |

Each POST is one match. Sending the same team again adds another match.

## Reading the leaderboard

- `GET /api/leaderboard`: teams in rank order, each with `rank`, `name`, `best`, `total`, `average` and `matches`.
- `GET /api/live`: everything the leaderboard page shows (teams, latest results, ranking mode, announcement, locked or not).

## Admin panel

The admin panel lives at a secret, unlinked address: `https://space-battle-teal.vercel.app/ops/<secret>`.
Following the challenge's security-through-obscurity rule, it has no login. Any wrong address
shows "page not found." **We'll give the secret address to the coordinator privately. It's
not written here or in the code.**

What the coordinator can do:

| Tool | What it does |
|---|---|
| Add a result | Type in a score by hand. Works even when the API is locked. |
| Edit / Delete | Fix or remove any single result. Delete asks "are you sure?" |
| Undo last delete | Brings back deleted results, newest first. |
| Fix a team name | Renames or merges a team's results (like "Nova" into "Nova Squad"). |
| Ranking | Rank by best single match (default), total points, or average per match. |
| Announcement | A message at the top of the leaderboard and big screen. |
| Lock / Unlock | Lock to freeze the final results. The API answers `423` while locked. |
| Download as CSV | A backup of every result. |
| Reset tournament | Deletes everything. You have to type RESET. |

## Credits

Built with Flask, Pico CSS 2.1.1 (amber theme, and every page is based on the Pico v2 "Preview"
example), the Orbitron font (Google Fonts), SQLite and Neon Postgres, hosted on Vercel.
Full list with licenses: `CREDITS.md`. AI use is disclosed in `CREDITS.md`.
