# database.py
# Every SQL statement in the project lives in this file.
#
# On your computer we use SQLite, which stores the whole database in one file and comes with Python.
# On Vercel, files are erased between requests, so there we use a Postgres database instead.
# If the DATABASE_URL setting exists we use Postgres, otherwise SQLite. The SQL is the same for both.

import os
import sqlite3
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

PROJECT_FOLDER = os.path.dirname(os.path.abspath(__file__))
database_file = os.path.join(PROJECT_FOLDER, "spacebattle.db")
database_url = os.environ.get("DATABASE_URL")
table_ready = False

# Errors from either database. app.py turns these into a friendly "database unavailable" page.
DATABASE_ERRORS = (sqlite3.Error, psycopg.Error)


def use_file(path):
    """Switch to a SQLite file (used by demo mode and the tests). Never touches Postgres."""
    global database_file, database_url, table_ready
    database_file = os.path.join(PROJECT_FOLDER, path)
    database_url = None
    table_ready = False


def using_postgres():
    return database_url is not None


def connect():
    """Open the database and make sure the table exists."""
    global table_ready
    if using_postgres():
        connection = psycopg.connect(database_url, row_factory=dict_row, connect_timeout=10)
        id_column = "BIGSERIAL PRIMARY KEY"
    else:
        # timeout makes a request wait its turn if another one is writing right now.
        connection = sqlite3.connect(database_file, timeout=15)
        connection.row_factory = sqlite3.Row  # lets us write row["score"]
        id_column = "INTEGER PRIMARY KEY AUTOINCREMENT"

    if not table_ready:
        connection.execute(f"""
            CREATE TABLE IF NOT EXISTS results (
                id             {id_column},
                name           TEXT   NOT NULL,
                score          BIGINT NOT NULL,
                submission_id  TEXT   UNIQUE,
                created_at     TEXT   NOT NULL,
                original_score BIGINT
            )
        """)
        connection.commit()
        table_ready = True
    return connection


def run(connection, sql, values=()):
    """Runs one SQL statement. SQLite marks blanks with ?, Postgres with %s."""
    if using_postgres():
        sql = sql.replace("?", "%s")
    return connection.execute(sql, values)


def now():
    """The current time as text, for example 2026-11-14T15:04:05.123+00:00"""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def add_result(name, score, submission_id=None, created_at=None):
    """Save one match. Returns the new row, or None if the submission_id was already used."""
    connection = connect()
    try:
        row = run(
            connection,
            "INSERT INTO results (name, score, submission_id, created_at) VALUES (?, ?, ?, ?) RETURNING *",
            (name, score, submission_id, created_at or now()),
        ).fetchone()
        connection.commit()
        return row
    except (sqlite3.IntegrityError, psycopg.errors.UniqueViolation):
        # UNIQUE means the database itself refuses a repeat, even if two arrive at once.
        return None
    finally:
        connection.close()


def get_result(result_id):
    connection = connect()
    row = run(connection, "SELECT * FROM results WHERE id = ?", (result_id,)).fetchone()
    connection.close()
    return row


def find_by_submission_id(submission_id):
    connection = connect()
    row = run(
        connection, "SELECT * FROM results WHERE submission_id = ?", (submission_id,)
    ).fetchone()
    connection.close()
    return row


def all_results():
    """Every match, oldest first."""
    connection = connect()
    rows = run(connection, "SELECT * FROM results ORDER BY id").fetchall()
    connection.close()
    return rows


def search_results(search_text, corrected_only, page, page_size):
    """One page of matches for the admin table. Returns (rows, total matching rows)."""
    # strpos and instr do the same job (find text inside text), but each database knows only one.
    find = "strpos" if using_postgres() else "instr"
    where = f"WHERE {find}(lower(name), lower(?)) > 0"
    if corrected_only:
        where += " AND original_score IS NOT NULL"

    connection = connect()
    total = run(
        connection, "SELECT COUNT(*) AS total FROM results " + where, (search_text,)
    ).fetchone()["total"]
    rows = run(
        connection,
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
    run(
        connection,
        "UPDATE results SET name = ?, score = ?, original_score = ? WHERE id = ?",
        (name, score, original, result_id),
    )
    connection.commit()
    connection.close()
    return True


def delete_result(result_id):
    connection = connect()
    cursor = run(connection, "DELETE FROM results WHERE id = ?", (result_id,))
    connection.commit()
    connection.close()
    return cursor.rowcount > 0


def delete_everything():
    """Remove every match. Returns how many were deleted."""
    connection = connect()
    cursor = run(connection, "DELETE FROM results")
    connection.commit()
    connection.close()
    return cursor.rowcount
