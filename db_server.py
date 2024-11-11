import sqlite3
import time

# Open a connection to the SQLite database
conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()

# Enable foreign keys for consistency (optional but good practice)
cursor.execute('PRAGMA foreign_keys = ON')

# Set a journal mode for better performance
cursor.execute('PRAGMA journal_mode = WAL')

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

# Create indexes for frequently queried columns
cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_xp_user_id ON user_xp (user_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_activity_user_id ON user_activity (user_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_xp_boost_cooldowns_user_id ON xp_boost_cooldowns (user_id)')

# Commit the changes
conn.commit()

# Function to analyze the query plan
def analyze_query(query, params=()):
    cursor.execute(f"EXPLAIN QUERY PLAN {query}", params)
    query_plan = cursor.fetchall()
    print("Query Plan:")
    for step in query_plan:
        print(step)

# Function to update user XP
def update_user_xp(user_id, total_xp):
    # Analyzing the SELECT query to check the user XP
    analyze_query("SELECT * FROM user_xp WHERE user_id = ?", (user_id,))
    
    cursor.execute("INSERT OR IGNORE INTO user_xp (user_id, xp) VALUES (?, ?)", (user_id, 0))
    cursor.execute("UPDATE user_xp SET xp = xp + ? WHERE user_id = ?", (total_xp, user_id))
    conn.commit()

# Function to track user activity for burst detection
def track_activity(user_id):
    current_time = time.time()

    # Analyzing the INSERT/REPLACE query for user activity
    analyze_query("INSERT OR REPLACE INTO user_activity (user_id, last_activity) VALUES (?, ?)", (user_id, current_time))
    
    cursor.execute("INSERT OR REPLACE INTO user_activity (user_id, last_activity) VALUES (?, ?)", (user_id, current_time))
    conn.commit()

# Function to handle XP boost cooldown
def check_boost_cooldown(user_id):
    current_time = time.time()

    # Analyzing the SELECT query for XP boost cooldown
    analyze_query("SELECT last_boost_time FROM xp_boost_cooldowns WHERE user_id = ?", (user_id,))
    
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

    # Analyzing the INSERT/REPLACE query for XP boost cooldown
    analyze_query("INSERT OR REPLACE INTO xp_boost_cooldowns (user_id, last_boost_time) VALUES (?, ?)", (user_id, current_time))
    
    cursor.execute("INSERT OR REPLACE INTO xp_boost_cooldowns (user_id, last_boost_time) VALUES (?, ?)", (user_id, current_time))
    conn.commit()

# Function to check activity bursts and handle XP boosts
def check_activity_burst(user_id):
    current_time = time.time()

    # Analyzing the SELECT query for last activity
    analyze_query("SELECT last_activity FROM user_activity WHERE user_id = ?", (user_id,))
    
    cursor.execute("SELECT last_activity FROM user_activity WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result:
        last_activity = result[0]
        if current_time - last_activity < 300:  # Activity burst within 5 minutes
            return True
    return False
