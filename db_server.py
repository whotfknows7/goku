import sqlite3
import time

# Connect to the SQLite database
conn = sqlite3.connect('database.db')  
cursor = conn.cursor()

# Create user_xp table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_xp (
        user_id INTEGER PRIMARY KEY,
        xp INTEGER DEFAULT 0
    )
''')

# Create user_activity table to track last message timestamps
cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_activity (
        user_id INTEGER PRIMARY KEY,
        last_activity REAL
    )
''')

# Create xp_boost_cooldowns table to track boost cooldowns
cursor.execute('''
    CREATE TABLE IF NOT EXISTS xp_boost_cooldowns (
        user_id INTEGER PRIMARY KEY,
        last_boost_time REAL
    )
''')

# Function to update user XP
def update_user_xp(user_id, xp_gain):
    cursor.execute("INSERT OR IGNORE INTO user_xp (user_id, xp) VALUES (?, ?)", (user_id, 0))
    cursor.execute("UPDATE user_xp SET xp = xp + ? WHERE user_id = ?", (xp_gain, user_id))
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
def check_activity_burst(user_id):
    current_time = time.time()
    cursor.execute("SELECT last_activity FROM user_activity WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result:
        last_activity = result[0]
        if current_time - last_activity < 300:  # Activity burst within 5 minutes
            return True
    return False

# Commit changes and close connection

    conn.commit()
    conn.close()
