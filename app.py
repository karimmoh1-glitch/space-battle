# app.py
# The web server. Each @app.route function answers one web address.
#
# Start the demo:      python app.py --demo
# Start for real:      python app.py

import hmac
import json
import os
import random
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

from flask import (Flask, Response, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)

import database
import rules

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024  # refuse requests over 10 KB
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # other websites cannot submit admin forms
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# Secrets come from the environment so they are never saved in the public code.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
ADMIN_PATH = os.environ.get("ADMIN_PATH")

DEMO_MODE = False
simulate_matches = False  # demo only: keep adding made-up matches
PAGE_SIZE = 25
RESET_PHRASE = "RESET TOURNAMENT"

# Replace these with your names before you submit.
TEAM_MEMBERS = ["Team member 1", "Team member 2"]


@app.template_filter("commas")
def add_commas(number):
    """Lets templates write {{ score | commas }} to show 1,250."""
    return "--" if number is None else f"{number:,}"


@app.context_processor
def add_template_variables():
    """Makes these variables available in every template."""
    return {"demo_mode": DEMO_MODE, "time_ago": rules.time_ago}


# ---------- Public pages ----------

@app.route("/")
def home():
    return render_template("index.html", page="home")


@app.route("/display")
def display():
    return render_template("display.html")


@app.route("/rules")
def rules_page():
    return render_template("rules.html", page="rules")


@app.route("/api-guide")
def api_guide():
    return render_template("api_guide.html", page="api")


@app.route("/about")
def about():
    return render_template("about.html", page="about", members=TEAM_MEMBERS)


def board_data():
    """Everything the live board needs, worked out from the saved matches."""
    if simulate_matches and random.random() < 0.35:
        add_demo_match()

    results = database.all_results()
    teams = rules.get_standings(results)

    # Find the matches that are a team's best, to mark them in the feed.
    best_scores = {team["key"]: team["best"] for team in teams}
    recent = []
    for result in reversed(results[-10:]):
        recent.append({
            "id": result["id"],
            "name": result["name"],
            "score": result["score"],
            "created_at": result["created_at"],
            "is_best": best_scores[result["name"].lower()] == result["score"],
        })

    # Only highlight a team for a short time after it plays.
    fresh_key = None
    moved_key, places_moved = None, 0
    if len(results) > 0 and rules.seconds_since(results[-1]["created_at"]) < 25:
        moved_key, places_moved = rules.rank_change(results)
        if rules.seconds_since(results[-1]["created_at"]) < 3.5:
            fresh_key = results[-1]["name"].lower()

    return {
        "teams": teams,
        "recent": recent,
        "stats": rules.get_stats(teams),
        "ships": rules.orbit_map(teams),
        "fresh_key": fresh_key,
        "moved_key": moved_key,
        "places_moved": places_moved,
    }


@app.route("/live/board")
def live_board():
    """The board as HTML. static/live.js swaps this into the page every 3 seconds."""
    return render_template("_board.html", **board_data())


@app.route("/live/display")
def live_display():
    return render_template("_display_board.html", **board_data())


# ---------- Public API ----------

@app.after_request
def allow_other_websites(response):
    """Lets tools hosted on other websites call the public API."""
    if request.path.startswith("/api/"):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def result_json(row):
    return {"id": row["id"], "name": row["name"], "score": row["score"],
            "createdAt": row["created_at"]}


def api_error(message, status):
    return jsonify({"ok": False, "error": message}), status


@app.route("/api/results", methods=["POST"])
def submit_result():
    """Saves one match result."""
    data = request.get_json(force=True, silent=True)
    if data is None:
        return api_error("Request body must be valid JSON.", 400)

    cleaned, error = rules.check_submission(data)
    if error:
        return api_error(error, 400)

    saved = database.add_result(cleaned["name"], cleaned["score"], cleaned["submission_id"])
    if saved is not None:
        return jsonify({"ok": True, "duplicate": False, "result": result_json(saved)}), 201

    # add_result returned None, so this submissionId has been used before.
    original = database.find_by_submission_id(cleaned["submission_id"])
    if original is None:
        return api_error("That submission was just removed. Please retry.", 503)

    same_name = original["name"].lower() == cleaned["name"].lower()
    if same_name and original["score"] == cleaned["score"]:
        return jsonify({"ok": True, "duplicate": True, "result": result_json(original)}), 200

    return api_error("This submissionId was already used with a different name or score.", 409)


@app.route("/api/leaderboard")
def leaderboard_api():
    """The standings as JSON."""
    results = database.all_results()
    teams = rules.get_standings(results)
    stats = rules.get_stats(teams)

    return jsonify({
        "teams": [{
            "rank": team["rank"],
            "tied": team["tied"],
            "name": team["name"],
            "bestScore": team["best"],
            "totalScore": str(team["total"]),  # text, because a sum can get very large
            "matches": team["matches"],
            "lastMatchAt": team["last_match"],
        } for team in teams],
        "recent": [result_json(row) for row in reversed(results[-10:])],
        "stats": {
            "teamCount": stats["teams"],
            "matchCount": stats["matches"],
            "topScore": stats["top_score"],
            "leadMargin": stats["lead"],
            "lastMatchAt": stats["last_match"],
        },
        "generatedAt": database.now(),
        "demo": DEMO_MODE,
    })


@app.route("/api/health")
def health():
    database.all_results()
    return jsonify({"ok": True})


# ---------- Hidden admin panel ----------

def check_admin_path(slug):
    """Pretend the admin pages do not exist unless the secret path is correct."""
    if ADMIN_PATH is None or ADMIN_PASSWORD is None or slug != ADMIN_PATH:
        abort(404)


def is_logged_in():
    return session.get("admin") is True


@app.route("/ops/<slug>/login", methods=["POST"])
def admin_login(slug):
    check_admin_path(slug)
    typed = request.form.get("password", "")
    # compare_digest takes the same time whether the guess is close or not.
    if hmac.compare_digest(typed.encode(), ADMIN_PASSWORD.encode()):
        session["admin"] = True
    else:
        flash("That password is not correct.", "error")
    return redirect(url_for("admin_panel", slug=slug))


@app.route("/ops/<slug>/logout", methods=["POST"])
def admin_logout(slug):
    check_admin_path(slug)
    session.clear()
    return redirect(url_for("admin_panel", slug=slug))


@app.route("/ops/<slug>")
def admin_panel(slug):
    check_admin_path(slug)
    if not is_logged_in():
        return render_template("admin_login.html", slug=slug)

    search_text = request.args.get("q", "").strip()
    corrected_only = request.args.get("corrected") == "on"
    page = max(request.args.get("page", 1, type=int), 1)
    edit_id = request.args.get("edit", type=int)

    rows, total = database.search_results(search_text, corrected_only, page, PAGE_SIZE)
    teams = rules.get_standings(database.all_results())

    return render_template(
        "admin.html", slug=slug, rows=rows, total=total, page=page,
        last_page=max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1),
        search_text=search_text, corrected_only=corrected_only, edit_id=edit_id,
        stats=rules.get_stats(teams), leader=teams[0]["name"] if teams else "--",
        reset_phrase=RESET_PHRASE,
    )


def read_score_form():
    """Checks the name and score typed into an admin form. Returns (name, score, error)."""
    name, error = rules.check_name(request.form.get("name", ""))
    if error:
        return None, None, error
    try:
        score = int(request.form.get("score", "").strip())
    except ValueError:
        return None, None, "Score must be a whole number."
    score, error = rules.check_score(score)
    return name, score, error


@app.route("/ops/<slug>/add", methods=["POST"])
def admin_add(slug):
    check_admin_path(slug)
    if not is_logged_in():
        abort(403)

    name, score, error = read_score_form()
    if error:
        flash(error, "error")
    else:
        database.add_result(name, score)
        flash(f"Added {score} for {name}.", "success")
    return redirect(url_for("admin_panel", slug=slug))


@app.route("/ops/<slug>/edit/<int:result_id>", methods=["POST"])
def admin_edit(slug, result_id):
    check_admin_path(slug)
    if not is_logged_in():
        abort(403)

    name, score, error = read_score_form()
    if error:
        flash(error, "error")
    elif database.update_result(result_id, name, score):
        flash(f"Result {result_id} corrected.", "success")
    else:
        flash("That result no longer exists.", "error")
    return redirect(url_for("admin_panel", slug=slug))


@app.route("/ops/<slug>/delete/<int:result_id>", methods=["POST"])
def admin_delete(slug, result_id):
    check_admin_path(slug)
    if not is_logged_in():
        abort(403)

    if database.delete_result(result_id):
        flash(f"Deleted result {result_id}.", "success")
    else:
        flash("That result no longer exists.", "error")
    return redirect(url_for("admin_panel", slug=slug))


@app.route("/ops/<slug>/reset", methods=["POST"])
def admin_reset(slug):
    global simulate_matches
    check_admin_path(slug)
    if not is_logged_in():
        abort(403)

    if request.form.get("confirm") == RESET_PHRASE:
        count = database.delete_everything()
        simulate_matches = False  # lets the demo show the empty board
        flash(f"Tournament reset. {count} results deleted.", "success")
    else:
        flash(f"Nothing was deleted. You must type {RESET_PHRASE} exactly.", "error")
    return redirect(url_for("admin_panel", slug=slug))


@app.route("/ops/<slug>/backup")
def admin_backup(slug):
    """Downloads every result as a JSON file."""
    check_admin_path(slug)
    if not is_logged_in():
        abort(403)

    backup = [dict(row) for row in database.all_results()]
    return Response(
        json.dumps(backup, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=space-battle-backup.json"},
    )


# ---------- Errors ----------

def wants_json():
    return request.path.startswith("/api/")


@app.errorhandler(sqlite3.Error)
def database_problem(error):
    app.logger.error("Database error: %s", error)
    if wants_json() or request.path.startswith("/live/"):
        return api_error("The database is unavailable. Please retry shortly.", 503)
    return render_template("error.html", title="System fault",
                           message="The database is unavailable. Please try again shortly."), 503


@app.errorhandler(404)
def not_found(error):
    if wants_json():
        return api_error("That address does not exist.", 404)
    return render_template("error.html", title="Off course",
                           message="That page is not on any known trajectory."), 404


@app.errorhandler(403)
def forbidden(error):
    return render_template("error.html", title="Access denied",
                           message="Please sign in again."), 403


@app.errorhandler(405)
def wrong_method(error):
    return api_error("That method is not allowed here.", 405)


@app.errorhandler(413)
def too_large(error):
    return api_error("Request body must be 10 KB or smaller.", 413)


@app.errorhandler(500)
def server_error(error):
    if wants_json():
        return api_error("Something went wrong on the server.", 500)
    return render_template("error.html", title="System fault",
                           message="Something went wrong on the server."), 500


# ---------- Demo mode ----------

DEMO_TEAMS = {
    "Kessler Syndicate": [214, 547, 263],
    "Apogee Squadron": [301, 438, 275, 165],
    "Meridian Array": [152, 297, 300, 438],
    "Halcyon Drift": [348, 112, 291],
    "Oort Cloud Runners": [342, 229, 215],
    "Vega Lancers": [337, 225, 206],
    "Perihelion Wing": [314, 271, 264],
    "Ceres Mining Guild": [261, 188, 139],
    "Titan Forge": [241, 177, 161],
    "Callisto Ghosts": [90, 44, 8],
    "Aphelion Riders": [74, 6, 63],
    "Europa Deep": [68, 55, 67],
    "Solar Flare Society": [67, 44],
    "Nightside Relay": [-35, -62, -18],
}


def add_demo_match():
    """Pretends a match just finished, so the demo board keeps moving."""
    name = random.choice(list(DEMO_TEAMS))
    database.add_result(name, random.randint(-40, 430))


def start_demo():
    """Switches to a separate file of made-up teams. Real results are never touched."""
    global DEMO_MODE, simulate_matches, ADMIN_PATH, ADMIN_PASSWORD
    DEMO_MODE = True
    simulate_matches = True
    ADMIN_PATH = "demo"
    ADMIN_PASSWORD = "demo"

    database.use_file("demo.db")
    database.delete_everything()

    minutes_ago = 60
    for name, scores in DEMO_TEAMS.items():
        for score in scores:
            time = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
            database.add_result(name, score, None, time.isoformat(timespec="milliseconds"))
            minutes_ago -= 1


if __name__ == "__main__":
    if "--demo" in sys.argv:
        start_demo()
        print("Demo running. Admin page: http://localhost:8000/ops/demo  (password: demo)")
    app.run(port=8000, threaded=True)
