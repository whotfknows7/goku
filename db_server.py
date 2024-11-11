import sqlite3
import time

# Open a connection to the SQLite database
conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()

# Create tables if they don't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_xp (
        user_id TEXT PRIMARY KEY,
        xp INTEGER
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_activity (
        user_id INTEGER PRIMARY KEY,
        last_activity REAL
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS xp_boost_cooldowns (
        user_id INTEGER PRIMARY KEY,
        last_boost_time REAL
    )
''')

# Create indexes on frequently queried columns (user_id)
cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id_xp ON user_xp (user_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id_activity ON user_activity (user_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id_boosts ON xp_boost_cooldowns (user_id)')

conn.commit()

# Function to update user XP
def update_user_xp(user_id, total_xp):
    cursor.execute("INSERT OR IGNORE INTO user_xp (user_id, xp) VALUES (?, ?)", (user_id, 0))
    cursor.execute("UPDATE user_xp SET xp = xp + ? WHERE user_id = ?", (total_xp, user_id))
    conn.commit()

# Function to track user activity for burst detection
def track_activity(user_id):
    current_time = time.time()
    cursor.execute("INSERT OR REPLACE INTO user_activity (user_id, last_activity) VALUES (?, ?)", (user_id, current_time))
    conn.commit()

# Function to handle XP boost cooldown
def check_boost_cooldown(user_id):
    current_time = time.time()
    cursor.execute("SELECT last_boost_time FROM xp_boost_cooldowns WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result:
        last_boost_time = result[0]
        if current_time - last_boost_time < 300:  # 5-minute cooldown
            return False
    return True

# Function to update the XP boost cooldown
def update_boost_cooldown(user_id):
    current_time = time.time()
    cursor.execute("INSERT OR REPLACE INTO xp_boost_cooldowns (user_id, last_boost_time) VALUES (?, ?)", (user_id, current_time))
    conn.commit()

# Function to check activity bursts and handle XP boosts
def check_activity_burst(user_id, message=None):
    current_time = time.time()
    cursor.execute("SELECT last_activity FROM user_activity WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result:
        last_activity = result[0]
        if current_time - last_activity < 300:  # Activity burst within 5 minutes
            return True
    return False
