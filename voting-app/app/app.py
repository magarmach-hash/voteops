import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432"),
    "database": os.environ.get("DB_NAME", "votingdb"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "password"),
}

VOTE_OPTIONS = [
    "We'll fix it in next sprint",
    "Let's schedule a meeting",
]


def get_db():
    return psycopg2.connect(**DB_CONFIG)


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id SERIAL PRIMARY KEY,
            option TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    app.logger.info("DB initialized")


with app.app_context():
    try:
        init_db()
    except Exception as e:
        app.logger.error(f"DB init failed: {e}")


@app.route("/")
def index():
    return render_template("index.html", options=VOTE_OPTIONS)


@app.route("/vote", methods=["POST"])
def vote():
    data = request.get_json()
    option = data.get("option", "").strip()
    if option not in VOTE_OPTIONS:
        return jsonify({"error": "Invalid option"}), 400
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO votes (option) VALUES (%s)", (option,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Vote recorded!"}), 201
    except Exception as e:
        app.logger.error(f"Vote error: {e}")
        return jsonify({"error": "DB error"}), 500


@app.route("/results")
def results():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT option, COUNT(*) as count
            FROM votes
            GROUP BY option
            ORDER BY count DESC
        """)
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) as total FROM votes")
        total = cur.fetchone()["total"]
        cur.close()
        conn.close()

        results_dict = {row["option"]: int(row["count"]) for row in rows}
        for opt in VOTE_OPTIONS:
            if opt not in results_dict:
                results_dict[opt] = 0

        return jsonify({"results": results_dict, "total": total})
    except Exception as e:
        app.logger.error(f"Results error: {e}")
        return jsonify({"error": "DB error"}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)






