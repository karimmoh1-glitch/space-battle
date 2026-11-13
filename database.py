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
    cursor = connection.execute(sql, values)
    rows = []
    if cursor.description is not None:  # only SELECT and RETURNING give back rows
        for row in cursor.fetchall():
            rows.append(dict(row))
    connection.commit()
    connection.close()
    return rows


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


# ---------- Results ----------

def add_result(name, score, created_at=None):
    if created_at is None:
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = run("INSERT INTO results (name, score, created_at) VALUES (?, ?, ?) RETURNING *",
               (name, score, created_at))
    return rows[0]


def all_results():
    """Every result, oldest first."""
    return run("SELECT * FROM results ORDER BY id")


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
    run("INSERT INTO deleted_results (name, score, created_at) VALUES (?, ?, ?)",
        (result["name"], result["score"], result["created_at"]))
    run("DELETE FROM results WHERE id = ?", (result_id,))


def undo_delete():
    """Brings back the most recently deleted result. Returns it, or None if the trash is empty."""
    rows = run("SELECT * FROM deleted_results ORDER BY id DESC LIMIT 1")
    if len(rows) == 0:
        return None
    result = rows[0]
    add_result(result["name"], result["score"], result["created_at"])
    run("DELETE FROM deleted_results WHERE id = ?", (result["id"],))
    return result


def trash_count():
    rows = run("SELECT COUNT(*) AS count FROM deleted_results")
    return rows[0]["count"]


def delete_all():
    """Reset: deletes every result and empties the trash. Can't be undone."""
    run("DELETE FROM results")
    run("DELETE FROM deleted_results")


# ---------- Settings ----------

def get_settings():
    """Returns all the admin settings as a dictionary, like {"mode": "best"}."""
    settings = {}
    for row in run("SELECT * FROM settings"):
        settings[row["name"]] = row["value"]
    return settings


def save_setting(name, value):
    run("DELETE FROM settings WHERE name = ?", (name,))
    run("INSERT INTO settings (name, value) VALUES (?, ?)", (name, value))
