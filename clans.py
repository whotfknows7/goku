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
