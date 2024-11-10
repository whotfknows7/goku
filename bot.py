import discord
from discord.ext import commands, tasks
from collections import defaultdict
import time
import re
import sqlite3
import asyncio

# Define your bot token and logging channel ID
TOKEN = 'MTMwMzQyNjkzMzU4MDc2MzIzNg.GbKOt1.KKnsqSNb-Z6e06AiGv6zkGFpW1alryMd-jCLBU'  # Replace with your bot token
ROLE_LOG_CHANNEL_ID = 1251143629943345204  # Replace with your role log channel ID
GENERAL_LOG_CHANNEL_ID = 1301183910838796460  # Replace with your general log channel ID

# Define intents
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Constants for XP boost and activity burst
BOOST_DURATION = 300  # 5 minutes in seconds
BOOST_COOLDOWN = 300  # 5 minutes in seconds
MESSAGE_LIMIT = 10
TIME_WINDOW = 300

# Regular expressions
URL_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
EMOJI_REGEX = r":([^:]+):"

# Database setup
conn = sqlite3.connect('/app/database.db')  # Ensure database is stored in Glitch's `/app` directory
cursor = conn.cursor()

# Create tables if not exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_xp (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_activity (
    user_id INTEGER PRIMARY KEY,
    last_activity REAL
)
""")
conn.commit()

# Function to update user XP in the database
def update_user_xp(user_id, xp_gain):
    cursor.execute("INSERT OR IGNORE INTO user_xp (user_id, xp) VALUES (?, ?)", (user_id, 0))
    cursor.execute("UPDATE user_xp SET xp = xp + ? WHERE user_id = ?", (xp_gain, user_id))
    conn.commit()

# Function to track user activity for burst
def track_activity(user_id):
    current_time = time.time()
    cursor.execute("INSERT OR REPLACE INTO user_activity (user_id, last_activity) VALUES (?, ?)", (user_id, current_time))
    conn.commit()

# Check for activity burst every 2 seconds
@tasks.loop(seconds=2)
async def check_activity_burst():
    current_time = time.time()
    cursor.execute("SELECT user_id, last_activity FROM user_activity")
    for user_id, last_activity in cursor.fetchall():
        if current_time - last_activity < TIME_WINDOW:
            # Apply XP boost logic if applicable
            pass  # Expand this logic as needed

@bot.event
async def on_ready():
    print(f"Bot has successfully logged in as {bot.user}")
    check_activity_burst.start()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    user_id = message.author.id
    filtered_content = re.sub(URL_REGEX, "", message.content)
    filtered_content = ''.join(c for c in filtered_content if c.isalnum() or c.isspace())

    character_xp = len(filtered_content.replace(" ", ""))
    emoji_xp = len(re.findall(EMOJI_REGEX, message.content)) * 5
    total_xp = character_xp + emoji_xp

    update_user_xp(user_id, total_xp)
    track_activity(user_id)
    await bot.process_commands(message)

ROLE_NAMES = {
    "🧔Homo Sapien": {
        "message": "🎉 Congrats {member.mention}! You've become a 🧔Homo Sapien and unlocked GIF permissions!",
        "has_perms": True
    },
    "🏆Homie": {
        "message": "🎉 Congrats {member.mention}! You've become a 🏆 Homie and unlocked Image permissions!",
        "has_perms": True
    },
    "🥉VETERAN": {
        "message": "🎉 Congrats {member.mention}! You've become a 🥉VETERAN!",
        "has_perms": False
    },
    "🥈ELITE": {
        "message": "🎉 Congrats {member.mention}! You've become an 🥈ELITE",
        "has_perms": False
    },
    "🥇MYTHIC": {
        "message": "🎉 Congrats {member.mention}! You've become a 🥇MYTHIC",
        "has_perms": False
    },
    "⭐VIP": {
        "message": "🎉 Congrats {member.mention}! You've become a ⭐VIP",
        "has_perms": False
    },
    "✨LEGENDARY": {
        "message": "🎉 Congrats {member.mention}! You've become a ✨LEGENDARY",
        "has_perms": False
    },
}


import os

db_path = "/app/database.db"

@bot.event
async def on_ready():
    if os.path.exists(db_path):
        print(f"Database file exists at: {db_path}")
    else:
        print(f"Database file not found at: {db_path}")

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        for role in after.roles:
            if role.name in ROLE_NAMES and role.name not in [r.name for r in before.roles]:
                await announce_role_update(after, role.name)

async def announce_role_update(member, role_name):
    role_info = ROLE_NAMES[role_name]
    log_channel = bot.get_channel(ROLE_LOG_CHANNEL_ID)
    await log_channel.send(role_info["message"].format(member=member))

bot.run(TOKEN)
