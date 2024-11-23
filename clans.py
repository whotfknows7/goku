import sqlite3
from db_server import fetch_top_10_users, save_daily_top_users
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
    