import sqlite3
import time
import asyncio
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
# Function to create clan role tables
def create_clan_role_tables():
    try:
        cursor.execute('''CREATE TABLE IF NOT EXISTS clan_role_1 (
            user_id TEXT PRIMARY KEY,
            xp INTEGER NOT NULL CHECK(xp >= 0)
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS clan_role_2 (
            user_id TEXT PRIMARY KEY,
            xp INTEGER NOT NULL CHECK(xp >= 0)
        )''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clan_role_1_user_id_xp ON clan_role_1 (user_id, xp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clan_role_2_user_id_xp ON clan_role_2 (user_id, xp)')

        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating clan role tables: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error creating clan role tables: {e}\n")

# Function to fetch top 10 users by XP
def fetch_top_10_users():
    try:
        cursor.execute("SELECT user_id, xp FROM user_xp ORDER BY xp DESC LIMIT 10")
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error fetching top 10 users: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error fetching top 10 users: {e}\n")
        return []

# Function to save top 10 users into the clan role tables
def save_top_10_users_to_clan_roles():
    top_10_users = fetch_top_10_users()
    for user_id, xp in top_10_users:
        # Check if user has either clan role 1 or clan role 2
        # Assuming you have some function to check user roles
        user_roles = get_user_roles(user_id)  # This is a placeholder for your role-fetching logic

        if 'clan_role_1' in user_roles:
            save_user_to_clan_role_table('clan_role_1', user_id, xp)
        elif 'clan_role_2' in user_roles:
            save_user_to_clan_role_table('clan_role_2', user_id, xp)

# Function to save user XP to the correct clan role table
def save_user_to_clan_role_table(clan_role_table, user_id, xp):
    try:
        cursor.execute(f"INSERT OR REPLACE INTO {clan_role_table} (user_id, xp) VALUES (?, ?)", (user_id, xp))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error saving XP for {user_id} in {clan_role_table}: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error saving XP for {user_id} in {clan_role_table}: {e}\n")

# Function to reset the database and save top 10 users data
async def reset_database_and_save_top_10():
    try:
        # Save the top 10 users to clan role tables before reset
        save_top_10_users_to_clan_roles()

        # Now reset the user_xp table
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute("DELETE FROM user_xp;")
        conn.commit()
        print("Database has been reset and top 10 users data has been saved.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error during reset and saving top 10 users data: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"Error during reset and saving top 10 users data: {e}\n")

async def reset_task():
    while True:
        await asyncio.sleep(86400)  # 86400 seconds = 24 hours
        await reset_database_and_save_top_10()
