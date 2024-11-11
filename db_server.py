import sqlite3
import time

# Database setup
db_path = '/app/database.db'
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

# Create tables if not exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_xp (
    user_id INTEGER PRIMARY KEY,
    xp REAL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_activity (
    user_id INTEGER PRIMARY KEY,
    last_activity REAL
)
""")

def update_user_xp(user_id, xp_gain):
    cursor.execute("INSERT OR IGNORE INTO user_xp (user_id, xp) VALUES (?, ?)", (user_id, 0))
    cursor.execute("UPDATE user_xp SET xp = xp + ? WHERE user_id = ?", (xp_gain, user_id))
    conn.commit()

def track_activity(user_id):
    current_time = time.time()
    cursor.execute("INSERT OR REPLACE INTO user_activity (user_id, last_activity) VALUES (?, ?)", (user_id, current_time))
    conn.commit()

# Ensure connection stays alive
def close_connection():
    conn.close()
