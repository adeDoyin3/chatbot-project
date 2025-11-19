# app.py
# CSC331 Project 2 - AI Query Web App (Flask backend)
# Author: <YOUR NAME / SURNAME MAT.NO>
# NOTE: This code is written to be compatible with older/transitional versions of the 
# google-generativeai Python SDK by using the GenerativeModel class explicitly.
# Set GEMINI_API_KEY in environment.

import os
import sqlite3
import datetime
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import google.generativeai as genai

# Load .env locally (Render will use environment variables)
load_dotenv()

# ---------------- Unique variable names ----------------
app_flask = Flask(__name__)
# Use a relative path from the script location
database_path = os.path.join(os.path.dirname(__file__), "queries.db") 
gemini_env_key = os.getenv("GEMINI_API_KEY")

# Configure Gemini SDK if key exists
if gemini_env_key:
    # This configuration is necessary for the top-level functions to work
    genai.configure(api_key=gemini_env_key)

# ---------------- Database Functions ----------------
def _init_db_if_missing():
    """Initializes the SQLite database and creates the 'queries' table if it doesn't exist."""
    conn_db = sqlite3.connect(database_path)
    cur_db = conn_db.cursor()
    cur_db.execute(
        """
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT,
            timestamp TEXT NOT NULL
        )
        """
    )
    conn_db.commit()
    conn_db.close()

_init_db_if_missing()

def _save_query_to_db(question_text: str, answer_text: str):
    """Saves a user query and the AI's response to the database."""
    conn_db = sqlite3.connect(database_path)
    cur_db = conn_db.cursor()
    cur_db.execute(
        "INSERT INTO queries (question, answer, timestamp) VALUES (?, ?, ?)",
        (question_text, answer_text, datetime.datetime.utcnow().isoformat())
    )
    conn_db.commit()
    conn_db.close()

def _clear_db_queries():
    """Deletes all entries from the queries table."""
    conn_db = sqlite3.connect(database_path)
    cur_db = conn_db.cursor()
    # DELETE FROM is generally safer than DROP TABLE if you want to keep the table structure
    cur_db.execute("DELETE FROM queries") 
    conn_db.commit()
    conn_db.close()

# ---------------- Routes ----------------
@app_flask.route("/")
def index_route():
    """Renders the main HTML template."""
    return render_template("index.html")


@app_flask.route("/ask", methods=["POST"])
def ask_route():
    """Handles AI query, calls Gemini, saves result, and returns response."""
    body_json = request.get_json(force=True)
    q_text = body_json.get("question", "").strip()
    
    if not q_text:
        return jsonify({"error": "Empty question"}), 400

    # Check API key before making the call
    if not gemini_env_key:
        answer_msg = "GEMINI_API_KEY is not set on the server. Set it as an environment variable."
        _save_query_to_db(q_text, answer_msg)
        return jsonify({"answer": answer_msg}), 500

    try:
        model_name = "gemini-2.5-flash"
        
        # --- FIX: Instantiate GenerativeModel and call .generate_content() on the instance.
        # This is the expected pattern for older SDK versions that don't expose 
        # Client or the top-level generate_content() function.
        gemini_model = genai.GenerativeModel(model_name)
        
        # Call generate_content on the model instance
        resp = gemini_model.generate_content(q_text)

        # Extract the text response (using the common .text property)
        answer_text = resp.text 

        # Save to DB
        _save_query_to_db(q_text, answer_text)

        return jsonify({"answer": answer_text})

    except Exception as exc:
        # Handle API or other unexpected errors
        err_msg = f"Error calling Gemini: {str(exc)}"
        _save_query_to_db(q_text, err_msg)
        return jsonify({"answer": err_msg}), 500


@app_flask.route("/history", methods=["GET"])
def history_route():
    """Retrieves the last 50 queries from the database."""
    conn_db = sqlite3.connect(database_path)
    # Allows fetching results as dictionary-like objects
    conn_db.row_factory = sqlite3.Row 
    cur_db = conn_db.cursor()
    cur_db.execute(
        "SELECT id, question, answer, timestamp FROM queries ORDER BY id DESC LIMIT 50"
    )
    rows = cur_db.fetchall()
    conn_db.close()
    
    # Convert rows to list of dictionaries
    items = [dict(r) for r in rows]
    return jsonify({"history": items})

@app_flask.route("/clear_history", methods=["POST"])
def clear_history_route():
    """Clears all query history from the database."""
    _clear_db_queries()
    return jsonify({"success": True, "message": "History cleared"}), 200


# ---------------- Run server ----------------
if __name__ == "__main__":
    app_flask.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=True
    )