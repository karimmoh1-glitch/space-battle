# database.py
# Every SQL statement in the project lives in this file.
# We use SQLite, which stores the whole database in one file and comes with Python.

import os
import sqlite3
from datetime import datetime, timezone

PROJECT_FOLDER = os.path.dirname(os.path.abspath(__file__))
database_file = os.path.join(PROJECT_FOLDER, "spacebattle.db")


def use_file(path):
    """Switch to a different database file (used by demo mode and the tests)."""
    global database_file
    database_file = os.path.join(PROJECT_FOLDER, path)


def connect():
    """Open the database and make sure the table exists."""
    # timeout makes a request wait its turn if another one is writing right now.
    connection = sqlite3.connect(database_file, timeout=15)
    connection.row_factory = sqlite3.Row  # lets us write row["score"]
    connection.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT    NOT NULL,
            score          INTEGER NOT NULL,
            submission_id  TEXT    UNIQUE,
            created_at     TEXT    NOT NULL,
            original_score INTEGER
        )
    """)
    return connection


def now():
    """The current time as text, for example 2026-11-14T15:04:05.123+00:00"""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def add_result(name, score, submission_id=None, created_at=None):
    """Save one match. Returns the new row, or None if the submission_id was already used."""
    connection = connect()
    try:
        cursor = connection.execute(
            "INSERT INTO results (name, score, submission_id, created_at) VALUES (?, ?, ?, ?)",
            (name, score, submission_id, created_at or now()),
        )
        connection.commit()
        return get_result(cursor.lastrowid)
    except sqlite3.IntegrityError:
        # UNIQUE means the database itself refuses a repeat, even if two arrive at once.
        return None
    finally:
        connection.close()


def get_result(result_id):
    connection = connect()
    row = connection.execute("SELECT * FROM results WHERE id = ?", (result_id,)).fetchone()
    connection.close()
    return row


def find_by_submission_id(submission_id):
    connection = connect()
    row = connection.execute(
        "SELECT * FROM results WHERE submission_id = ?", (submission_id,)
    ).fetchone()
    connection.close()
    return row


def all_results():
    """Every match, oldest first."""
    connection = connect()
    rows = connection.execute("SELECT * FROM results ORDER BY id").fetchall()
    connection.close()
    return rows


def search_results(search_text, corrected_only, page, page_size):
    """One page of matches for the admin table. Returns (rows, total matching rows)."""
    where = "WHERE instr(lower(name), lower(?)) > 0"
    if corrected_only:
        where += " AND original_score IS NOT NULL"

    connection = connect()
    total = connection.execute(
        "SELECT COUNT(*) FROM results " + where, (search_text,)
    ).fetchone()[0]
    rows = connection.execute(
        "SELECT * FROM results " + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
        (search_text, page_size, (page - 1) * page_size),
    ).fetchall()
    connection.close()
    return rows, total


def update_result(result_id, name, score):
    """Correct a match. The first original score is kept so a mistake can be traced."""
    row = get_result(result_id)
    if row is None:
        return False

    original = row["original_score"]
    if original is None and score != row["score"]:
        original = row["score"]

    connection = connect()
    connection.execute(
        "UPDATE results SET name = ?, score = ?, original_score = ? WHERE id = ?",
        (name, score, original, result_id),
    )
    connection.commit()
    connection.close()
    return True


def delete_result(result_id):
    connection = connect()
    cursor = connection.execute("DELETE FROM results WHERE id = ?", (result_id,))
    connection.commit()
    connection.close()
    return cursor.rowcount > 0


def delete_everything():
    """Remove every match. Returns how many were deleted."""
    connection = connect()
    cursor = connection.execute("DELETE FROM results")
    connection.commit()
    connection.close()
    return cursor.rowcount
