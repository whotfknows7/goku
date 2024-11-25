
import sqlite3
import time
import asyncio
from util import save_user_to_clan_role_table

GUILD_ID = 1227505156220784692  # Replace with your actual guild ID
CLAN_ROLE_1_ID = 1245407423917854754  # Replace with your actual Clan Role 1 ID
CLAN_ROLE_2_ID = 1247225208700665856
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
         
# Function to reset the database and perform the save operation
async def reset_and_save_top_users():
    await save_user_to_clan_role_table  # Save the top 10 users' XP before reset
    await reset_database
    # Reset the user_xp table
    cursor.execute("DELETE FROM user_xp;")
    conn.commit()
    print("XP data reset and top users saved.")

# Example of running the reset task every 24 hours
async def reset_task():
    while True:
        await asyncio.sleep(22)  # Sleep for 24 hours (86400 seconds)
        await reset_and_save_top_users()