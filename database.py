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


def create_table():
    if DATABASE_URL:
        id_column = "SERIAL PRIMARY KEY"
    else:
        id_column = "INTEGER PRIMARY KEY AUTOINCREMENT"

    run(f"""CREATE TABLE IF NOT EXISTS results (
        id {id_column},
        name TEXT NOT NULL,
        score BIGINT NOT NULL,
        created_at TEXT NOT NULL
    )""")


def add_result(name, score):
    time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = run("INSERT INTO results (name, score, created_at) VALUES (?, ?, ?) RETURNING *",
               (name, score, time))
    return rows[0]


def all_results():
    return run("SELECT * FROM results ORDER BY id")


def get_result(result_id):
    rows = run("SELECT * FROM results WHERE id = ?", (result_id,))
    if len(rows) == 0:
        return None
    return rows[0]


def update_result(result_id, name, score):
    run("UPDATE results SET name = ?, score = ? WHERE id = ?", (name, score, result_id))


def delete_result(result_id):
    run("DELETE FROM results WHERE id = ?", (result_id,))


def delete_all():
    run("DELETE FROM results")
