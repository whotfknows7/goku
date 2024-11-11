from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

# Initialize database and setup user_data table
def setup_database():
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_data (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER DEFAULT 0,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.commit()
    connection.close()

setup_database()

# Route to get XP leaderboard
@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute("SELECT user_id, xp FROM user_data ORDER BY xp DESC LIMIT 10")
    rows = cursor.fetchall()
    connection.close()
    return jsonify(rows)

# Route to update user XP
@app.route("/update_xp", methods=["POST"])
def update_xp():
    data = request.json
    user_id = data["user_id"]
    xp = data["xp"]

    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute("""
        INSERT INTO user_data (user_id, xp)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET xp = xp + ?""", (user_id, xp, xp))
    connection.commit()
    connection.close()
    return {"status": "XP updated successfully"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
