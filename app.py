# app.py
# The web server for the Space Battle leaderboard.
# Run it on your computer with:  python app.py   then open http://localhost:8000

import os
import sqlite3

import psycopg
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session

import database
import rules

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024  # turn away anything bigger than 10 KB
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # other websites can't use our admin forms

# The secrets are set on the server, not written in the code, because the code is public.
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
ADMIN_PATH = os.environ.get("ADMIN_PATH")

database.create_table()


# ---------- Public pages ----------

@app.route("/")
def leaderboard():
    results = database.all_results()
    teams = rules.get_standings(results)
    return render_template("index.html", teams=teams, match_count=len(results))


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
    teams = rules.get_standings(database.all_results())
    return jsonify(teams)


# ---------- Admin ----------

def check_admin_path(path):
    # If the secrets aren't set, or the path is wrong, act like the page doesn't exist.
    if ADMIN_PASSWORD is None or ADMIN_PATH is None or path != ADMIN_PATH:
        abort(404)


def logged_in():
    return session.get("admin") == True


def read_form():
    """Gets the name and score from an admin form. Returns (name, score, error)."""
    name = request.form.get("name", "")
    try:
        score = int(request.form.get("score", ""))
    except ValueError:
        return None, None, "Score must be a whole number."

    error = rules.check_result({"name": name, "score": score})
    return rules.clean_name(name), score, error


@app.route("/ops/<path>", methods=["GET", "POST"])
def admin(path):
    check_admin_path(path)

    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
        else:
            flash("Wrong password.")
        return redirect(f"/ops/{path}")

    if not logged_in():
        return render_template("admin_login.html")

    results = database.all_results()
    results.reverse()  # newest first
    return render_template("admin.html", results=results, path=path)


@app.route("/ops/<path>/add", methods=["POST"])
def admin_add(path):
    check_admin_path(path)
    if not logged_in():
        abort(403)

    name, score, error = read_form()
    if error:
        flash(error)
    else:
        database.add_result(name, score)
        flash(f"Added {score} for {name}.")
    return redirect(f"/ops/{path}")


@app.route("/ops/<path>/edit/<int:result_id>", methods=["GET", "POST"])
def admin_edit(path, result_id):
    check_admin_path(path)
    if not logged_in():
        abort(403)

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
        return redirect(f"/ops/{path}")

    return render_template("edit.html", result=result, path=path)


@app.route("/ops/<path>/delete/<int:result_id>", methods=["POST"])
def admin_delete(path, result_id):
    check_admin_path(path)
    if not logged_in():
        abort(403)

    database.delete_result(result_id)
    flash(f"Result #{result_id} deleted.")
    return redirect(f"/ops/{path}")


@app.route("/ops/<path>/reset", methods=["POST"])
def admin_reset(path):
    check_admin_path(path)
    if not logged_in():
        abort(403)

    if request.form.get("confirm") == "RESET":
        database.delete_all()
        flash("The tournament was reset. Every result was deleted.")
    else:
        flash("Nothing was deleted. Type RESET to confirm.")
    return redirect(f"/ops/{path}")


@app.route("/ops/<path>/logout", methods=["POST"])
def admin_logout(path):
    session.clear()
    return redirect("/")


# ---------- Errors ----------

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Not found."}), 404
    return render_template("error.html", message="That page doesn't exist."), 404


@app.errorhandler(403)
def not_allowed(error):
    return render_template("error.html", message="Please log in first."), 403


@app.errorhandler(sqlite3.Error)
@app.errorhandler(psycopg.Error)
def database_error(error):
    print("Database error:", error)
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "The database is down. Try again soon."}), 503
    return render_template("error.html", message="The database is down. Try again soon."), 503


if __name__ == "__main__":
    app.run(port=8000, debug=True)
