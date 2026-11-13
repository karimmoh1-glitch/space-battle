# app.py
# The web server for the Space Battle leaderboard.
# Run it on your computer with:  python app.py   then open http://localhost:8000

import csv
import io
import os
import sqlite3

import psycopg
from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request

import database
import rules

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024  # turn away anything bigger than 10 KB

# Set on the server, not written in the code, because the code is public.
# SECRET_KEY signs the little "Saved!" messages on the admin page.
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
# The challenge asks for "security through obscurity": the admin page has no login,
# it just lives at an address nobody is told about.
ADMIN_PATH = os.environ.get("ADMIN_PATH")

MAX_ANNOUNCEMENT_LENGTH = 120
TICKER_SIZE = 8

database.create_tables()


def board_data():
    """Everything the leaderboard pages need, in one dictionary."""
    results = database.all_results()
    settings = database.get_settings()

    mode = settings.get("mode", "best")
    if mode not in rules.MODE_LABELS:
        mode = "best"

    return {
        "mode": mode,
        "mode_label": rules.MODE_LABELS[mode],
        "locked": settings.get("locked") == "yes",
        "announcement": settings.get("announcement", ""),
        "match_count": len(results),
        "teams": rules.get_standings(results, mode),
        "recent": rules.recent_results(results, TICKER_SIZE),
    }


# ---------- Public pages ----------

@app.route("/")
def leaderboard():
    return render_template("index.html", **board_data())


@app.route("/display")
def display():
    # The big-screen version for the projector.
    return render_template("display.html", **board_data())


@app.route("/rules")
def rules_page():
    return render_template("rules.html")


@app.route("/api-guide")
def api_guide():
    return render_template("api_guide.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ---------- API ----------

@app.route("/api/results", methods=["POST"])
def add_result():
    if database.get_settings().get("locked") == "yes":
        return jsonify({"ok": False, "error": "Results are locked. The tournament is over."}), 423

    # force=True reads JSON even if the sender forgot the Content-Type header.
    # silent=True gives None instead of crashing if the JSON is broken.
    data = request.get_json(force=True, silent=True)
    error = rules.check_result(data)
    if error:
        return jsonify({"ok": False, "error": error}), 400

    result = database.add_result(rules.clean_name(data["name"]), data["score"])
    return jsonify({"ok": True, "result": result}), 201


@app.route("/api/leaderboard")
def leaderboard_json():
    return jsonify(board_data()["teams"])


@app.route("/api/live")
def live_json():
    # live.js asks for this every 5 seconds to update the page.
    return jsonify(board_data())


# ---------- Admin ----------

def check_admin_path(path):
    # If the secret isn't set, or the path is wrong, act like the page doesn't exist.
    if ADMIN_PATH is None or path != ADMIN_PATH:
        abort(404)


def back_to_admin(path):
    return redirect(f"/ops/{path}")


def read_form():
    """Gets the name and score from an admin form. Returns (name, score, error)."""
    name = request.form.get("name", "")
    try:
        score = int(request.form.get("score", ""))
    except ValueError:
        return None, None, "Score must be a whole number."

    error = rules.check_result({"name": name, "score": score})
    return rules.clean_name(name), score, error


@app.route("/ops/<path>")
def admin(path):
    check_admin_path(path)
    board = board_data()
    results = database.all_results()
    results.reverse()  # newest first
    return render_template("admin.html", path=path, results=results, board=board,
                           modes=rules.MODE_LABELS, trash_count=database.trash_count())


@app.route("/ops/<path>/add", methods=["POST"])
def admin_add(path):
    check_admin_path(path)
    name, score, error = read_form()
    if error:
        flash(error)
    else:
        database.add_result(name, score)
        flash(f"Added {score} for {name}.")
    return back_to_admin(path)


@app.route("/ops/<path>/edit/<int:result_id>", methods=["GET", "POST"])
def admin_edit(path, result_id):
    check_admin_path(path)
    result = database.get_result(result_id)
    if result is None:
        abort(404)

    if request.method == "POST":
        name, score, error = read_form()
        if error:
            flash(error)
            return redirect(f"/ops/{path}/edit/{result_id}")
        database.update_result(result_id, name, score)
        flash(f"Result #{result_id} updated.")
        return back_to_admin(path)

    return render_template("edit.html", result=result, path=path)


@app.route("/ops/<path>/delete/<int:result_id>", methods=["POST"])
def admin_delete(path, result_id):
    check_admin_path(path)
    database.delete_result(result_id)
    flash(f"Result #{result_id} deleted. Use Undo if that was a mistake.")
    return back_to_admin(path)


@app.route("/ops/<path>/undo", methods=["POST"])
def admin_undo(path):
    check_admin_path(path)
    result = database.undo_delete()
    if result is None:
        flash("There's nothing to undo.")
    else:
        flash(f"Brought back {result['score']} for {result['name']}.")
    return back_to_admin(path)


@app.route("/ops/<path>/merge", methods=["POST"])
def admin_merge(path):
    check_admin_path(path)
    old_name = request.form.get("old_name", "")
    new_name = rules.clean_name(request.form.get("new_name", ""))

    error = rules.check_result({"name": new_name, "score": 0})
    if error:
        flash(error)
    else:
        changed = database.rename_team(old_name, new_name)
        flash(f"Renamed {changed} result(s) from {old_name} to {new_name}.")
    return back_to_admin(path)


@app.route("/ops/<path>/mode", methods=["POST"])
def admin_mode(path):
    check_admin_path(path)
    mode = request.form.get("mode")
    if mode in rules.MODE_LABELS:
        database.save_setting("mode", mode)
        flash(f"Teams are now ranked by {rules.MODE_LABELS[mode]}.")
    return back_to_admin(path)


@app.route("/ops/<path>/lock", methods=["POST"])
def admin_lock(path):
    check_admin_path(path)
    if request.form.get("locked") == "yes":
        database.save_setting("locked", "yes")
        flash("Results are locked. The API won't take new scores.")
    else:
        database.save_setting("locked", "no")
        flash("Results are unlocked. The API is taking scores again.")
    return back_to_admin(path)


@app.route("/ops/<path>/announce", methods=["POST"])
def admin_announce(path):
    check_admin_path(path)
    message = request.form.get("message", "").strip()
    if len(message) > MAX_ANNOUNCEMENT_LENGTH:
        flash("Announcements must be 120 characters or less.")
    else:
        database.save_setting("announcement", message)
        if message == "":
            flash("Announcement cleared.")
        else:
            flash("Announcement posted.")
    return back_to_admin(path)


@app.route("/ops/<path>/export.csv")
def admin_export(path):
    check_admin_path(path)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "score", "created_at"])
    for result in database.all_results():
        name = result["name"]
        # Excel runs cells that start with = + - @ as formulas, so add a ' in front.
        if name[0] in "=+-@":
            name = "'" + name
        writer.writerow([result["id"], name, result["score"], result["created_at"]])

    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=space-battle-results.csv"})


@app.route("/ops/<path>/reset", methods=["POST"])
def admin_reset(path):
    check_admin_path(path)
    if request.form.get("confirm") == "RESET":
        database.delete_all()
        flash("The tournament was reset. Every result was deleted.")
    else:
        flash("Nothing was deleted. Type RESET to confirm.")
    return back_to_admin(path)


# ---------- Errors ----------

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Not found."}), 404
    return render_template("error.html", message="That page doesn't exist."), 404


@app.errorhandler(sqlite3.Error)
@app.errorhandler(psycopg.Error)
def database_error(error):
    print("Database error:", error)
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "The database is down. Try again soon."}), 503
    return render_template("error.html", message="The database is down. Try again soon."), 503


if __name__ == "__main__":
    app.run(port=8000, debug=True)
