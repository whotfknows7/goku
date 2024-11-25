import sqlite3
import time
import asyncio

# Assuming you have the function `has_either_role_by_ids` in the same file or imported.

# Constants for guild and clan role IDs
GUILD_ID = 1227505156220784692  # Replace with your actual guild ID
CLAN_ROLE_1_ID = 1245407423917854754  # Replace with your actual Clan Role 1 ID
CLAN_ROLE_2_ID = 1247225208700665856  # Replace with your actual Clan Role 2 ID

DATABASE_PATH = 'database.db'  # Path to your database file

# Open a connection to the SQLite database
conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
cursor = conn.cursor()

# Create tables for user XP and clan roles
def create_tables():
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_xp (
                user_id TEXT PRIMARY KEY,
                xp INTEGER NOT NULL CHECK(xp >= 0)
            )
        ''')

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

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id_xp ON user_xp (user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clan_role_1_user_id_xp ON clan_role_1 (user_id, xp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clan_role_2_user_id_xp ON clan_role_2 (user_id, xp)')
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating tables: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error creating tables: {e}\n")

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

# Function to save/update user XP in the correct clan role table
async def save_user_to_clan_role_table(bot, user_id, xp):
    try:
        # Check if the user has the relevant clan role using the bot
        has_role_1 = await bot.has_either_role_by_ids(user_id, CLAN_ROLE_1_ID, CLAN_ROLE_2_ID)

        if has_role_1:
            # Determine the correct table based on the clan role
            if await bot.has_either_role_by_ids(user_id, CLAN_ROLE_1_ID, CLAN_ROLE_2_ID):
                clan_role = 'clan_role_1'
            else:
                clan_role = 'clan_role_2'

            # Check if the user already exists in the table
            cursor.execute(f"SELECT xp FROM {clan_role} WHERE user_id = ?", (user_id,))
            existing_xp = cursor.fetchone()

            if existing_xp:
                # User exists, update their XP
                new_xp = existing_xp[0] + xp
                cursor.execute(f"UPDATE {clan_role} SET xp = ? WHERE user_id = ?", (new_xp, user_id))
            else:
                # New user, insert their XP
                cursor.execute(f"INSERT INTO {clan_role} (user_id, xp) VALUES (?, ?)", (user_id, xp))

            # Commit the changes to the database
            conn.commit()
            print(f"XP for user {user_id} updated in {clan_role} table.")
        else:
            print(f"User {user_id} does not have the correct role.")
    except sqlite3.Error as e:
        print(f"Error saving XP for user {user_id} in the clan role table: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error saving XP for user {user_id} in the clan role table: {e}\n")

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
async def reset_and_save_top_users(bot):
    await save_user_to_clan_role_table(bot)  # Save the top 10 users' XP before reset

    # Reset the user_xp table
    cursor.execute("DELETE FROM user_xp;")
    conn.commit()
    print("XP data reset and top users saved.")

# Example of running the reset task every 24 hours
async def reset_task():
    while True:
        await asyncio.sleep(86400)  # Sleep for 24 hours (86400 seconds)
        await reset_and_save_top_users()

# Start the process
create_tables()
