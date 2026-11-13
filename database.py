# database.py
# All the SQL for the project.
#
# On my computer, results are saved in a file called spacebattle.db (SQLite).
# On Vercel, files get erased, so the live site uses a Postgres database instead.
# If DATABASE_URL is set we use Postgres, otherwise we use the file.

import os
import sqlite3
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_FILE = os.path.join(os.path.dirname(__file__), "spacebattle.db")


def connect():
    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    connection = sqlite3.connect(DATABASE_FILE, timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


def run(sql, values=()):
    """Runs one SQL command and returns the rows as a list of dictionaries."""
    # SQLite uses ? for blanks and Postgres uses %s.
    if DATABASE_URL:
        sql = sql.replace("?", "%s")

    connection = connect()
    try:
        cursor = connection.execute(sql, values)
        rows = []
        if cursor.description is not None:  # only SELECT and RETURNING give back rows
            for row in cursor.fetchall():
                rows.append(dict(row))
        connection.commit()
    finally:
        connection.close()  # close it even if the SQL had an error
    return rows


def run_together(commands):
    """Runs a list of (sql, values) commands as one transaction. Either all of them
    happen or none of them do, so a crash can't leave things half done."""
    connection = connect()
    try:
        for sql, values in commands:
            if DATABASE_URL:
                sql = sql.replace("?", "%s")
            connection.execute(sql, values)
        connection.commit()
    finally:
        connection.close()  # if anything failed, closing without commit undoes all of it


def add_column(table, column):
    """Adds a column to a table that was made by an older version of this code."""
    if DATABASE_URL:
        run(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} TEXT")
    else:
        try:
            run(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
        except sqlite3.OperationalError:
            pass  # SQLite says "duplicate column" if it's already there


def create_tables():
    if DATABASE_URL:
        id_column = "SERIAL PRIMARY KEY"
    else:
        id_column = "INTEGER PRIMARY KEY AUTOINCREMENT"

    # Every match result.
    run(f"""CREATE TABLE IF NOT EXISTS results (
        id {id_column},
        name TEXT NOT NULL,
        score BIGINT NOT NULL,
        created_at TEXT NOT NULL
    )""")

    # Deleted results go here first, so the admin can undo a delete.
    run(f"""CREATE TABLE IF NOT EXISTS deleted_results (
        id {id_column},
        name TEXT NOT NULL,
        score BIGINT NOT NULL,
        created_at TEXT NOT NULL
    )""")

    # Admin choices, like the ranking mode and whether results are locked.
    run("""CREATE TABLE IF NOT EXISTS settings (
        name TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""")

    # match_id is an optional ID the game sends with each result. If the same match is
    # sent twice (like when the game retries after a timeout), we only save it once.
    # The UNIQUE index makes the database itself refuse a second copy.
    add_column("results", "match_id")
    add_column("deleted_results", "match_id")
    run("CREATE UNIQUE INDEX IF NOT EXISTS results_match_id ON results (match_id)")


# ---------- Results ----------

def add_result(name, score, match_id=None, created_at=None):
    """Saves a result. Returns (result, is_new). If a result with the same match_id
    was already saved, nothing new is saved and the old result comes back instead."""
    if created_at is None:
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # ON CONFLICT DO NOTHING: if the match_id is already taken, skip the insert.
    rows = run("""INSERT INTO results (name, score, created_at, match_id) VALUES (?, ?, ?, ?)
                  ON CONFLICT (match_id) DO NOTHING RETURNING *""",
               (name, score, created_at, match_id))
    if len(rows) == 1:
        return rows[0], True

    rows = run("SELECT * FROM results WHERE match_id = ?", (match_id,))
    return rows[0], False


def all_results():
    """Every result, oldest first."""
    return run("SELECT * FROM results ORDER BY id")


def team_results(name):
    """Every result for one team, oldest first. Capital letters don't matter."""
    return run("SELECT * FROM results WHERE LOWER(name) = LOWER(?) ORDER BY id", (name,))


def get_result(result_id):
    rows = run("SELECT * FROM results WHERE id = ?", (result_id,))
    if len(rows) == 0:
        return None
    return rows[0]


def update_result(result_id, name, score):
    run("UPDATE results SET name = ?, score = ? WHERE id = ?", (name, score, result_id))


def rename_team(old_name, new_name):
    """Renames every result for a team. Used to merge "Nova" and "Nova Squad".
    Returns how many results were changed."""
    rows = run("UPDATE results SET name = ? WHERE LOWER(name) = LOWER(?) RETURNING id",
               (new_name, old_name))
    return len(rows)


def delete_result(result_id):
    """Moves one result to the trash."""
    result = get_result(result_id)
    if result is None:
        return
    run_together([
        ("INSERT INTO deleted_results (name, score, created_at, match_id) VALUES (?, ?, ?, ?)",
         (result["name"], result["score"], result["created_at"], result["match_id"])),
        ("DELETE FROM results WHERE id = ?", (result_id,)),
    ])


def undo_delete():
    """Brings back the most recently deleted result. Returns it, or None if the trash is empty."""
    rows = run("SELECT * FROM deleted_results ORDER BY id DESC LIMIT 1")
    if len(rows) == 0:
        return None
    result = rows[0]
    run_together([
        ("""INSERT INTO results (name, score, created_at, match_id) VALUES (?, ?, ?, ?)
            ON CONFLICT (match_id) DO NOTHING""",
         (result["name"], result["score"], result["created_at"], result["match_id"])),
        ("DELETE FROM deleted_results WHERE id = ?", (result["id"],)),
    ])
    return result


def trash_count():
    rows = run("SELECT COUNT(*) AS count FROM deleted_results")
    return rows[0]["count"]


def delete_all():
    """Reset: deletes every result and empties the trash. Can't be undone."""
    run_together([
        ("DELETE FROM results", ()),
        ("DELETE FROM deleted_results", ()),
    ])


# ---------- Settings ----------

def get_settings():
    """Returns all the admin settings as a dictionary, like {"mode": "best"}."""
    settings = {}
    for row in run("SELECT * FROM settings"):
        settings[row["name"]] = row["value"]
    return settings


def save_setting(name, value):
    run_together([
        ("DELETE FROM settings WHERE name = ?", (name,)),
        ("INSERT INTO settings (name, value) VALUES (?, ?)", (name, value)),
    ])
