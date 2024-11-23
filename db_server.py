import sqlite3
import time
import asyncio
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

# Function to fetch top 10 users by XP from the user_xp table
def fetch_top_10_users():
    try:
        cursor.execute("SELECT user_id, xp FROM user_xp ORDER BY xp DESC LIMIT 10")
        return cursor.fetchall()  # Returns a list of tuples (user_id, xp)
    except sqlite3.Error as e:
        print(f"Error fetching top 10 users: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error fetching top 10 users: {e}\n")
        return []

# Asynchronous function to get user roles from the guild
async def get_user_roles(user_id):
    try:
        guild = client.get_guild(GUILD_ID)  # Get the guild using the predefined GUILD_ID
        if guild is None:
            print(f"Guild with ID {GUILD_ID} not found.")
            return []

        member = guild.get_member(user_id)  # Get the member by user ID
        if member is None:
            print(f"User {user_id} not found in the guild.")
            return []

        # Get the role IDs the user has
        user_roles = [role.id for role in member.roles]

        return user_roles  # List of role IDs for the user
    except discord.DiscordException as e:
        print(f"Error fetching roles for user {user_id}: {e}")
        return []

# Function to save/update user XP in the correct clan role table
def save_user_to_clan_role_table(user_id, xp, clan_role):
    try:
        # Determine the correct table based on the clan role
        if clan_role == 'clan_role_1':
            table_name = 'clan_role_1'
        elif clan_role == 'clan_role_2':
            table_name = 'clan_role_2'
        else:
            print(f"Unknown clan role: {clan_role}")
            return

        # Check if the user already exists in the table
        cursor.execute(f"SELECT xp FROM {table_name} WHERE user_id = ?", (user_id,))
        existing_xp = cursor.fetchone()

        if existing_xp:
            # User exists, update their XP
            new_xp = existing_xp[0] + xp
            cursor.execute(f"UPDATE {table_name} SET xp = ? WHERE user_id = ?", (new_xp, user_id))
        else:
            # New user, insert their XP
            cursor.execute(f"INSERT INTO {table_name} (user_id, xp) VALUES (?, ?)", (user_id, xp))

        conn.commit()
        print(f"XP for user {user_id} updated in {clan_role} table.")

    except sqlite3.Error as e:
        print(f"Error saving XP for user {user_id} in {clan_role}: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error saving XP for user {user_id} in {clan_role}: {e}\n")

# Main logic to process and save top 10 users' XP
async def save_top_10_users():
    top_users = fetch_top_10_users()  # Get the top 10 users based on XP
    for user_id, xp in top_users:
        # Get the user's roles
        user_roles = await get_user_roles(user_id)

        # Check if the user has the Clan Role 1 or Clan Role 2
        if CLAN_ROLE_1_ID in user_roles:
            # Save or update the XP in Clan Role 1 table
            save_user_to_clan_role_table(user_id, xp, 'clan_role_1')
        elif CLAN_ROLE_2_ID in user_roles:
            # Save or update the XP in Clan Role 2 table
            save_user_to_clan_role_table(user_id, xp, 'clan_role_2')
        else:
            print(f"User {user_id} doesn't have a valid clan role.")
            
# Function to reset the database and perform the save operation
async def reset_and_save_top_users():
    await save_top_10_users()  # Save the top 10 users' XP before reset
    
    # Reset the user_xp table
    cursor.execute("DELETE FROM user_xp;")
    conn.commit()
    print("XP data reset and top users saved.")

# Example of running the reset task every 24 hours
async def reset_task():
    while True:
        await asyncio.sleep(30)  # Sleep for 24 hours (86400 seconds)
        await reset_and_save_top_users()