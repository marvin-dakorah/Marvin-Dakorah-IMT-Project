# =============================================================
# app.py — Flask backend for the Climate Temperature Tracker
#
# Flask is a lightweight Python web framework. It maps URLs
# ("routes") to Python functions, and those functions return
# HTML (or JSON) back to the browser.
# =============================================================

import sqlite3                        # Built-in Python library for SQLite
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import date

# --- App setup -----------------------------------------------
# Flask(__name__) creates the application object.
# __name__ tells Flask where to look for templates and static files.
app = Flask(__name__)

# flash() needs a secret key to sign session cookies securely.
# In production, load this from an environment variable instead!
app.secret_key = "change-me-in-production"

# Path to our SQLite database file on disk
DATABASE = "climate.db"


# --- Database helpers ----------------------------------------

def get_db():
    """
    Opens a connection to the SQLite database and returns it.
    We use check_same_thread=False because Flask can serve multiple
    requests, but SQLite connections are normally single-thread.
    """
    conn = sqlite3.connect(DATABASE)

    # Row factory lets us access columns by name (row["city"])
    # instead of by index (row[1]), which is much more readable.
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Reads schema.sql and executes it against the database.
    Called once when the app starts to make sure the table exists.
    """
    with get_db() as conn:
        with open("schema.sql", "r") as f:
            # executescript() runs multiple SQL statements at once
            conn.executescript(f.read())


# --- Routes --------------------------------------------------
# A "route" maps a URL path to a Python function.
# The @app.route decorator registers the function with Flask.

@app.route("/", methods=["GET", "POST"])
def index():
    """
    GET  /  → Show the form + chart with all existing readings.
    POST /  → Validate and save a new reading, then redirect.

    We handle both methods in one function to keep things simple.
    The pattern "POST → redirect → GET" (PRG) prevents duplicate
    submissions if the user refreshes the page.
    """

    if request.method == "POST":
        # ── Handle form submission ──────────────────────────
        # request.form is a dict of values the browser sent
        city        = request.form.get("city", "").strip()
        temperature = request.form.get("temperature", "").strip()
        reading_date = request.form.get("date", "").strip()

        # Basic server-side validation — never trust the browser alone
        errors = []
        if not city:
            errors.append("City is required.")
        if not temperature:
            errors.append("Temperature is required.")
        else:
            try:
                temperature = float(temperature)   # convert string → number
            except ValueError:
                errors.append("Temperature must be a number.")

        if not reading_date:
            reading_date = date.today().isoformat()  # fallback to today

        if errors:
            for error in errors:
                flash(error, "error")               # queue error messages
            return redirect(url_for("index"))       # back to form

        # ── Save to database ────────────────────────────────
        # We use a "with" block so the connection closes automatically
        # and the transaction is committed (saved) on success.
        with get_db() as conn:
            conn.execute(
                # Use ? placeholders — NEVER format user data into SQL
                # directly, as that opens you up to SQL injection attacks.
                "INSERT INTO readings (city, temperature, date) VALUES (?, ?, ?)",
                (city, temperature, reading_date),
            )
            # conn.__exit__ calls conn.commit() automatically here

        flash(f"Reading for {city} saved!", "success")

        # Redirect to GET so refreshing won't resubmit the form (PRG pattern)
        return redirect(url_for("index"))

    # ── GET: fetch existing readings to display ─────────────
    with get_db() as conn:
        # Fetch all readings sorted by date ascending (oldest first)
        # so the chart's X-axis flows left → right in time.
        readings = conn.execute(
            "SELECT * FROM readings ORDER BY date ASC, id ASC"
        ).fetchall()

        # Get a list of distinct cities for the filter dropdown
        cities = conn.execute(
            "SELECT DISTINCT city FROM readings ORDER BY city"
        ).fetchall()

    # render_template() loads templates/index.html and fills in
    # the variables we pass as keyword arguments.
    return render_template(
        "index.html",
        readings=readings,
        cities=cities,
        # Pass today's date so the form's date input is pre-filled
        today=date.today().isoformat(),   # → "2025-06-13"
    )


@app.route("/delete/<int:reading_id>", methods=["POST"])
def delete(reading_id):
    """
    POST /delete/<id> → Delete one reading by its ID.

    We accept only POST (not GET) to prevent accidental deletion
    if a browser or search bot visits the URL.
    <int:reading_id> tells Flask to capture the number from the URL
    and pass it into the function as an integer.
    """
    with get_db() as conn:
        conn.execute("DELETE FROM readings WHERE id = ?", (reading_id,))
    flash("Reading deleted.", "success")
    return redirect(url_for("index"))


@app.route("/api/readings")
def api_readings():
    """
    GET /api/readings → Returns readings as JSON.
    Optional query param: ?city=London  to filter by city.

    This is a simple REST endpoint. The chart JS could call this
    instead of embedding data in HTML — useful as the app grows.
    """
    from flask import jsonify
    city_filter = request.args.get("city")   # ?city=... from URL

    with get_db() as conn:
        if city_filter:
            rows = conn.execute(
                "SELECT * FROM readings WHERE city = ? ORDER BY date ASC",
                (city_filter,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM readings ORDER BY date ASC"
            ).fetchall()

    # sqlite3.Row isn't JSON-serialisable by default, so we convert
    # each row to a plain Python dict first.
    return jsonify([dict(row) for row in rows])


# --- Entry point ---------------------------------------------
if __name__ == "__main__":
    init_db()           # Create table if it doesn't exist yet
    # debug=True reloads the server on code changes and shows
    # helpful error pages — turn this OFF in production!
    app.run(debug=True)