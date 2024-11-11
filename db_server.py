import sqlite3
import time
import queue
import threading

# Create a connection pool (simple implementation using queue)
class SQLiteConnectionPool:
    def __init__(self, db_file, pool_size=5):
        self.db_file = db_file
        self.pool = queue.Queue(pool_size)
        self.lock = threading.Lock()  # To synchronize access to the pool
        for _ in range(pool_size):
            conn = sqlite3.connect(self.db_file, check_same_thread=False, timeout=5)
            conn.row_factory = sqlite3.Row  # Enables access to columns by name
            self.pool.put(conn)

    def get_connection(self):
        with self.lock:
            return self.pool.get()

    def release_connection(self, conn):
        with self.lock:
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

# Function to update user XP (wrapped in a transaction with retry)
def update_user_xp(user_id, total_xp, retries=3):
    conn = pool.get_connection()
    cursor = conn.cursor()

    try:
        conn.execute('BEGIN TRANSACTION')  # Start a transaction

        # Update the XP (no redundant query execution)
        cursor.execute("INSERT OR IGNORE INTO user_xp (user_id, xp) VALUES (?, ?)", (user_id, 0))
        cursor.execute("UPDATE user_xp SET xp = xp + ? WHERE user_id = ?", (total_xp, user_id))
        conn.commit()  # Commit the transaction

    except sqlite3.DatabaseError as e:
        conn.rollback()  # Rollback in case of error
        print(f"Error updating user XP for {user_id}: {e}")
        if retries > 0:
            print("Retrying...")
            return update_user_xp(user_id, total_xp, retries - 1)  # Retry on failure
        else:
            print("Max retries reached, operation failed.")

    finally:
        pool.release_connection(conn)

# Function to track user activity for burst detection
def track_activity(user_id):
    conn = pool.get_connection()
    cursor = conn.cursor()

    try:
        current_time = time.time()

        # Update or Insert the activity (replace if already exists)
        cursor.execute("INSERT OR REPLACE INTO user_activity (user_id, last_activity) VALUES (?, ?)", (user_id, current_time))
        conn.commit()

    except sqlite3.DatabaseError as e:
        print(f"Error tracking activity for {user_id}: {e}")

    finally:
        pool.release_connection(conn)

# Function to handle XP boost cooldown with retry mechanism
def check_boost_cooldown(user_id, retries=3):
    conn = pool.get_connection()
    cursor = conn.cursor()

    try:
        current_time = time.time()

        # Get the last boost time and check cooldown
        cursor.execute("SELECT last_boost_time FROM xp_boost_cooldowns WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result:
            last_boost_time = result[0]
            if current_time - last_boost_time < 300:  # 5-minute cooldown
                return False
        return True

    except sqlite3.DatabaseError as e:
        print(f"Error checking boost cooldown for {user_id}: {e}")
        if retries > 0:
            print("Retrying...")
            return check_boost_cooldown(user_id, retries - 1)  # Retry on failure
        else:
            print("Max retries reached, operation failed.")
            return True

    finally:
        pool.release_connection(conn)

# Function to update the XP boost cooldown with retry mechanism
def update_boost_cooldown(user_id, retries=3):
    conn = pool.get_connection()
    cursor = conn.cursor()

    try:
        current_time = time.time()

        # Update or Insert the boost cooldown record (replace if exists)
        cursor.execute("INSERT OR REPLACE INTO xp_boost_cooldowns (user_id, last_boost_time) VALUES (?, ?)", (user_id, current_time))
        conn.commit()

    except sqlite3.DatabaseError as e:
        print(f"Error updating boost cooldown for {user_id}: {e}")
        if retries > 0:
            print("Retrying...")
            return update_boost_cooldown(user_id, retries - 1)  # Retry on failure
        else:
            print("Max retries reached, operation failed.")

    finally:
        pool.release_connection(conn)

# Function to check activity bursts and handle XP boosts
def check_activity_burst(user_id, message=None):
    conn = pool.get_connection()
    cursor = conn.cursor()

    try:
        current_time = time.time()

        # Check the last activity and determine if it's within the burst time
        cursor.execute("SELECT last_activity FROM user_activity WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result:
            last_activity = result[0]
            if current_time - last_activity < 300:  # Activity burst within 5 minutes
                return True
        return False

    except sqlite3.DatabaseError as e:
        print(f"Error checking activity burst for {user_id}: {e}")
        return False

    finally:
        pool.release_connection(conn)

# Example usage
update_user_xp("user123", 10)
track_activity("user123")
check_boost_cooldown("user123")
update_boost_cooldown("user123")
