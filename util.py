import sqlite3
import time
from bot import has_either_role_by_ids
# Database connection details
DATABASE_PATH = 'database.db'  # Path to your database file

# Connect to the database
conn = sqlite3.connect(DATABASE_PATH)
cursor = conn.cursor()

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
