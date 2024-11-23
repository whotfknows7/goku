import sqlite3
import time
import asyncio


CLAN_ROLE_1_ID = 1247225208700665856  # Replace with your actual role ID
CLAN_ROLE_2_ID = 1245407423917854754  # Replace with your actual role ID

# Open a connection to the SQLite database
conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()

# Create the user_xp table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_xp (
        user_id TEXT PRIMARY KEY,
        xp INTEGER NOT NULL CHECK(xp >= 0)  -- Ensure XP is never negative
    )
''')

conn.commit()

# Create an index on user_id for faster queries
cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id_xp ON user_xp (user_id)')
conn.commit()

# Function to delete user data
def delete_user_data(user_id):
    try:
        cursor.execute("DELETE FROM user_xp WHERE user_id = ?", (user_id,))
        conn.commit()
        print(f"Deleted data for user {user_id} who is no longer in the guild.")
    except sqlite3.Error as e:
        print(f"Error deleting user data for {user_id}: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error deleting user data for {user_id}: {e}\n")

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
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error updating XP for {user_id}: {e}\n")

# Function to clean up invalid users
def cleanup_invalid_users():
    try:
        cursor.execute("BEGIN TRANSACTION;")
        # Remove users with negative XP
        cursor.execute("DELETE FROM user_xp WHERE xp < 0")
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error during cleanup: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error during cleanup: {e}\n")

# Function to check database integrity
def check_database_integrity():
    try:
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        if result[0] == "ok":
            print("Database integrity check passed.")
        else:
            print(f"Database integrity check failed: {result}")
            with open("error_log.txt", "a") as log_file:
                log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Database integrity check failed: {result}\n")
    except sqlite3.Error as e:
        print(f"Error performing integrity check: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error performing integrity check: {e}\n")

# Function to bulk update XP
def update_bulk_xp(user_xp_data):
    try:
        cursor.execute("BEGIN TRANSACTION;")
        cursor.executemany("INSERT OR REPLACE INTO user_xp (user_id, xp) VALUES (?, ?)", user_xp_data)
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error bulk updating XP: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error bulk updating XP: {e}\n")

     
def fetch_top_10_users():
    """
    Fetch the top 10 users with the highest XP from the daily XP database.
    Returns a list of tuples (user_id, xp).
    """
    try:
        cursor.execute("""
        SELECT user_id, xp
        FROM user_xp
        ORDER BY xp DESC
        LIMIT 10
        """)
        return cursor.fetchall()  # List of tuples (user_id, xp)
    except sqlite3.Error as e:
        print(f"Error fetching top users: {e}")
        return []
          

# Function to reset the database (clear all XP data)
async def reset_database():
    try:
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute("DELETE FROM user_xp;")  # Clears all XP data
        conn.commit()
        print("Database has been reset.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error resetting the database: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"Error resetting the database: {e}\n")
            
