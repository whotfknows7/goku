import sqlite3
import time
import queue
import threading

# Create a connection pool (simple implementation using queue)
class SQLiteConnectionPool:
    def __init__(self, db_file, pool_size=5):
        self.db_file = db_file
        self.pool = queue.Queue(pool_size)
        for _ in range(pool_size):
            conn = sqlite3.connect(self.db_file, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # Enables access to columns by name
            self.pool.put(conn)

    def get_connection(self):
        return self.pool.get()

    def release_connection(self, conn):
        self.pool.put(conn)

# Initialize the connection pool
db_file = 'database.db'
pool = SQLiteConnectionPool(db_file)

# Function to analyze the query plan
def analyze_query(cursor, query, params=()):
    cursor.execute(f"EXPLAIN QUERY PLAN {query}", params)
    query_plan = cursor.fetchall()
    print("Query Plan:")
    for step in query_plan:
        print(step)

# Function to update user XP (wrapped in a transaction)
def update_user_xp(user_id, total_xp):
    conn = pool.get_connection()
    cursor = conn.cursor()

    try:
        conn.execute('BEGIN TRANSACTION')  # Start a transaction

        # Analyzing the SELECT query to check the user XP
        analyze_query(cursor, "SELECT * FROM user_xp WHERE user_id = ?", (user_id,))

        # Update the XP (no redundant query execution)
        cursor.execute("INSERT OR IGNORE INTO user_xp (user_id, xp) VALUES (?, ?)", (user_id, 0))
        cursor.execute("UPDATE user_xp SET xp = xp + ? WHERE user_id = ?", (total_xp, user_id))
        conn.commit()  # Commit the transaction

    except Exception as e:
        conn.rollback()  # Rollback in case of error
        print(f"Error updating user XP for {user_id}: {e}")

    finally:
        pool.release_connection(conn)

# Function to track user activity for burst detection
def track_activity(user_id):
    conn = pool.get_connection()
    cursor = conn.cursor()

    try:
        current_time = time.time()

        # Analyzing the INSERT/REPLACE query for user activity
        analyze_query(cursor, "INSERT OR REPLACE INTO user_activity (user_id, last_activity) VALUES (?, ?)", (user_id, current_time))

        cursor.execute("INSERT OR REPLACE INTO user_activity (user_id, last_activity) VALUES (?, ?)", (user_id, current_time))
        conn.commit()

    except Exception as e:
        print(f"Error tracking activity for {user_id}: {e}")

    finally:
        pool.release_connection(conn)

# Function to handle XP boost cooldown
def check_boost_cooldown(user_id):
    conn = pool.get_connection()
    cursor = conn.cursor()

    try:
        current_time = time.time()

        # Analyzing the SELECT query for XP boost cooldown
        analyze_query(cursor, "SELECT last_boost_time FROM xp_boost_cooldowns WHERE user_id = ?", (user_id,))

        cursor.execute("SELECT last_boost_time FROM xp_boost_cooldowns WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result:
            last_boost_time = result[0]
            if current_time - last_boost_time < 300:  # 5-minute cooldown
                return False
        return True

    except Exception as e:
        print(f"Error checking boost cooldown for {user_id}: {e}")
        return True

    finally:
        pool.release_connection(conn)

# Function to update the XP boost cooldown
def update_boost_cooldown(user_id):
    conn = pool.get_connection()
    cursor = conn.cursor()

    try:
        current_time = time.time()

        # Analyzing the INSERT/REPLACE query for XP boost cooldown
        analyze_query(cursor, "INSERT OR REPLACE INTO xp_boost_cooldowns (user_id, last_boost_time) VALUES (?, ?)", (user_id, current_time))

        cursor.execute("INSERT OR REPLACE INTO xp_boost_cooldowns (user_id, last_boost_time) VALUES (?, ?)", (user_id, current_time))
        conn.commit()

    except Exception as e:
        print(f"Error updating boost cooldown for {user_id}: {e}")

    finally:
        pool.release_connection(conn)

# Function to check activity bursts and handle XP boosts
def check_activity_burst(user_id):
    conn = pool.get_connection()
    cursor = conn.cursor()

    try:
        current_time = time.time()

        # Analyzing the SELECT query for last activity
        analyze_query(cursor, "SELECT last_activity FROM user_activity WHERE user_id = ?", (user_id,))

        cursor.execute("SELECT last_activity FROM user_activity WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result:
            last_activity = result[0]
            if current_time - last_activity < 300:  # Activity burst within 5 minutes
                return True
        return False

    except Exception as e:
        print(f"Error checking activity burst for {user_id}: {e}")
        return False

    finally:
        pool.release_connection(conn)

# Example usage
update_user_xp("user123", 10)
track_activity("user123")
check_boost_cooldown("user123")
update_boost_cooldown("user123")
import sqlite3
import time
import queue
import threading

