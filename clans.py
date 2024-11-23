import sqlite3

conn = sqlite3.connect("clan_roles.db")
cursor = conn.cursor()

# Create tables for clan roles
cursor.execute("""
CREATE TABLE IF NOT EXISTS clan_role_1 (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS clan_role_2 (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER
)
""")
conn.commit()
async def save_daily_top_users():
    # Assuming you have a function to fetch leaderboard data
    top_users = fetch_top_10_users()  # Returns a list of tuples (user_id, xp)

    for user_id, xp in top_users:
        user = await bot.fetch_user(user_id)  # Fetch user object from their ID
        roles = [role.id for role in user.roles]  # List of role IDs for the user

        if CLAN_ROLE_1_ID in roles:  # Replace with the actual ID
            save_to_clan_table("1247225208700665856", user_id, xp)
        elif CLAN_ROLE_2_ID in roles:  # Replace with the actual ID
            save_to_clan_table("1245407423917854754", user_id, xp)

def save_to_clan_table(table_name, user_id, xp):
    try:
        cursor.execute(f"""
        INSERT INTO {table_name} (user_id, xp)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET xp = excluded.xp
        """, (user_id, xp))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error saving data to {table_name}: {e}")
