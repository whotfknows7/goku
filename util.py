import sqlite3
import time
import asyncio

# Constants
GUILD_ID = 1227505156220784692  # Replace with your actual guild ID
CLAN_ROLE_1_ID = 1245407423917854754  # Replace with your actual Clan Role 1 ID
CLAN_ROLE_2_ID = 1247225208700665856
DATABASE_PATH = 'database.db'  # Path to your database file

# Connect to the SQLite database
conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
cursor = conn.cursor()

# Initialize tables and indexes
def initialize_database():
    try:
        # Create user_xp table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_xp (
                user_id TEXT PRIMARY KEY,
                xp INTEGER NOT NULL CHECK(xp >= 0)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id_xp ON user_xp (user_id)')

        # Create clan role tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clan_role_1 (
                user_id TEXT PRIMARY KEY,
                xp INTEGER NOT NULL CHECK(xp >= 0)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clan_role_2 (
                user_id TEXT PRIMARY KEY,
                xp INTEGER NOT NULL CHECK(xp >= 0)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clan_role_1_user_id_xp ON clan_role_1 (user_id, xp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clan_role_2_user_id_xp ON clan_role_2 (user_id, xp)')

        conn.commit()
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}")
        log_error(f"Error initializing database: {e}")

def log_error(message):
    with open("error_log.txt", "a") as log_file:
        log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

# Function to delete user data
def delete_user_data(user_id):
    try:
        cursor.execute("DELETE FROM user_xp WHERE user_id = ?", (user_id,))
        conn.commit()
        print(f"Deleted data for user {user_id}.")
    except sqlite3.Error as e:
        log_error(f"Error deleting user data for {user_id}: {e}")

# Function to update user XP with transaction management
def update_user_xp(user_id, total_xp):
    try:
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute("INSERT OR IGNORE INTO user_xp (user_id, xp) VALUES (?, ?)", (user_id, 0))
        cursor.execute("UPDATE user_xp SET xp = xp + ? WHERE user_id = ?", (total_xp, user_id))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        log_error(f"Error updating XP for user {user_id}: {e}")

# Function to clean up invalid users
def cleanup_invalid_users():
    try:
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute("DELETE FROM user_xp WHERE xp < 0")  # Remove users with negative XP
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        log_error(f"Error during cleanup: {e}")

# Function to check database integrity
def check_database_integrity():
    try:
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        if result[0] == "ok":
            print("Database integrity check passed.")
        else:
            print(f"Database integrity check failed: {result}")
            log_error(f"Database integrity check failed: {result}")
    except sqlite3.Error as e:
        log_error(f"Error performing integrity check: {e}")

# Function to bulk update XP
def update_bulk_xp(user_xp_data):
    try:
        cursor.execute("BEGIN TRANSACTION;")
        cursor.executemany("INSERT OR REPLACE INTO user_xp (user_id, xp) VALUES (?, ?)", user_xp_data)
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        log_error(f"Error bulk updating XP: {e}")

# Function to reset the database (clear all XP data)
async def reset_database():
    try:
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute("DELETE FROM user_xp;")
        conn.commit()
        print("Database has been reset.")
    except sqlite3.Error as e:
        conn.rollback()
        log_error(f"Error resetting the database: {e}")

# Function to save/update user XP in the correct clan role table
async def save_user_to_clan_role_table(bot, user_id, xp):
    try:
        has_role_1 = await bot.has_either_role_by_ids(user_id, CLAN_ROLE_1_ID, CLAN_ROLE_2_ID)

        if has_role_1:
            # Determine the correct table
            clan_role = 'clan_role_1' if await bot.has_either_role_by_ids(user_id, CLAN_ROLE_1_ID, CLAN_ROLE_2_ID) else 'clan_role_2'

            cursor.execute(f"SELECT xp FROM {clan_role} WHERE user_id = ?", (user_id,))
            existing_xp = cursor.fetchone()

            if existing_xp:
                cursor.execute(f"UPDATE {clan_role} SET xp = ? WHERE user_id = ?", (existing_xp[0] + xp, user_id))
            else:
                cursor.execute(f"INSERT INTO {clan_role} (user_id, xp) VALUES (?, ?)", (user_id, xp))

            conn.commit()
            print(f"XP for user {user_id} updated in {clan_role} table.")
        else:
            print(f"User {user_id} does not have the correct role.")
    except sqlite3.Error as e:
        log_error(f"Error saving XP for user {user_id} in the clan role table: {e}")

# Function to reset and save top users
async def reset_and_save_top_users(bot):
    await save_user_to_clan_role_table(bot, None, None)  # Save the top 10 users' XP before reset
    try:
        cursor.execute("DELETE FROM user_xp;")
        conn.commit()
        print("XP data reset and top users saved.")
    except sqlite3.Error as e:
        log_error(f"Error resetting the database: {e}")

# Example of running the reset task every 24 hours
async def reset_task(bot):
    while True:
        await asyncio.sleep(86400)  # Sleep for 24 hours
        await reset_and_save_top_users(bot)

# Initialize the database on script run
initialize_database()
