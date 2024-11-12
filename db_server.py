import sqlite3
import time

# Open a connection to the SQLite database
conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_xp (
        user_id TEXT PRIMARY KEY,
        xp INTEGER NOT NULL CHECK(xp >= 0)  -- Ensure XP is never negative
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_activity (
        user_id INTEGER PRIMARY KEY,
        last_activity REAL NOT NULL CHECK(last_activity > 0)  -- Ensure valid activity timestamps
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS xp_boost_cooldowns (
        user_id INTEGER PRIMARY KEY,
        last_boost_time REAL NOT NULL CHECK(last_boost_time > 0)  -- Ensure valid boost timestamps
    )
''')

conn.commit()


# Create indexes on frequently queried columns (user_id)
cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id_xp ON user_xp (user_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id_activity ON user_activity (user_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id_boosts ON xp_boost_cooldowns (user_id)')

conn.commit()

# Function to update user XP with transaction management
def update_user_xp(user_id, total_xp):
    try:
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute("INSERT OR IGNORE INTO user_xp (user_id, xp) VALUES (?, ?)", (user_id, 0))
        cursor.execute("UPDATE user_xp SET xp = xp + ? WHERE user_id = ?", (total_xp, user_id))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error updating XP for user {user_id}: {e}")
        # Optionally, log the error to a file
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"Error updating XP for user {user_id}: {e}\n")

# Function to track user activity for burst detection
def track_activity(user_id):
    try:
        cursor.execute("BEGIN TRANSACTION;")
        current_time = time.time()
        cursor.execute("INSERT OR REPLACE INTO user_activity (user_id, last_activity) VALUES (?, ?)", (user_id, current_time))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error tracking activity for user {user_id}: {e}")
        # Optionally, log the error to a file
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"Error tracking activity for user {user_id}: {e}\n")

# Function to handle XP boost cooldown
boost_cooldown_cache = {}

def check_boost_cooldown(user_id):
    if user_id in boost_cooldown_cache:
        last_boost_time = boost_cooldown_cache[user_id]
        if time.time() - last_boost_time < 300:  # 5-minute cooldown
            return False
    else:
        cursor.execute("SELECT last_boost_time FROM xp_boost_cooldowns WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            last_boost_time = result[0]
            boost_cooldown_cache[user_id] = last_boost_time
            if time.time() - last_boost_time < 300:
                return False
    return True


# Function to update the XP boost cooldown
def update_boost_cooldown(user_id):
    try:
        cursor.execute("BEGIN TRANSACTION;")
        current_time = time.time()
        cursor.execute("INSERT OR REPLACE INTO xp_boost_cooldowns (user_id, last_boost_time) VALUES (?, ?)", (user_id, current_time))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error updating boost cooldown for user {user_id}: {e}")
        # Optionally, log the error to a file
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"Error updating boost cooldown for user {user_id}: {e}\n")
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
def cleanup_invalid_users():
    try:
        cursor.execute("BEGIN TRANSACTION;")

        # Remove users with negative XP
        cursor.execute("DELETE FROM user_xp WHERE xp < 0")
        conn.commit()

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error during cleanup: {e}")
        # Optionally, log the error to a file
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"Error during cleanup: {e}\n")
def check_database_integrity():
    try:
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        if result[0] == "ok":
            print("Database integrity check passed.")
        else:
            print(f"Database integrity check failed: {result}")
            # Log the issue if needed
            with open("error_log.txt", "a") as log_file:
                log_file.write(f"Database integrity check failed: {result}\n")
    except sqlite3.Error as e:
        print(f"Error performing integrity check: {e}")
        # Optionally, log the error to a file
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"Error performing integrity check: {e}\n")
def update_bulk_xp(user_xp_data):
    try:
        cursor.execute("BEGIN TRANSACTION;")
        # Prepare the data for batch insertion
        cursor.executemany("INSERT OR REPLACE INTO user_xp (user_id, xp) VALUES (?, ?)", user_xp_data)
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error bulk updating XP: {e}")
        # Optionally, log the error to a file
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"Error bulk updating XP: {e}\n")