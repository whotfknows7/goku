import sqlite3
from db_server import fetch_top_10_users
conn = sqlite3.connect("clan_roles.db", check_same_thread=False)

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
    """
    Fetch the top 10 users of the day and save their XP to the respective clan role table.
    """
    top_users = fetch_top_10_users()  # Fetch top 10 users from daily XP database

    for user_id, xp in top_users:
        guild = bot.get_guild(GUILD_ID)  # Replace GUILD_ID with your actual guild/server ID
        member = guild.get_member(user_id)  # Fetch member object from guild

        if member:
            roles = [role.id for role in member.roles]  # List of role IDs for the member

            if CLAN_ROLE_1_ID in roles:  # Replace with the actual clan role ID
                save_to_clan_table("1245407423917854754", user_id, xp)
            elif CLAN_ROLE_2_ID in roles:  # Replace with the actual clan role ID
                save_to_clan_table("1247225208700665856", user_id, xp)
                
def save_to_clan_table(table_name, user_id, xp):
    """
    Save the user_id and XP to the specified clan role table.
    Updates the XP if the user already exists.
    """
    try:
        cursor.execute(f"""
        INSERT INTO {table_name} (user_id, xp)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET xp = excluded.xp
        """, (user_id, xp))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error saving data to {table_name}: {e}")
