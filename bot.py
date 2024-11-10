import discord
from discord.ext import commands, tasks
from collections import defaultdict
import time
import re
import json
import asyncio
import os
import shutil

# Define your bot token and logging channel ID
TOKEN = 'MTMwMzQyNjkzMzU4MDc2MzIzNg.GbKOt1.KKnsqSNb-Z6e06AiGv6zkGFpW1alryMd-jCLBU'  # Replace with your bot token
ROLE_LOG_CHANNEL_ID = 1251143629943345204  # Replace with the ID of the channel for role-related logs
GENERAL_LOG_CHANNEL_ID = 1301183910838796460  # Channel for all other logs

# Define intents
intents = discord.Intents.default()
intents.members = True  # Enable the members intent to listen to member updates

bot = commands.Bot(command_prefix="!", intents=intents)

# Regular expression to detect URLs
URL_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"

# Constants for XP boost and activity burst
BOOST_DURATION = 300  # 5 minutes in seconds
BOOST_COOLDOWN = 300  # 5 minutes in seconds
MESSAGE_LIMIT = 10    # Messages within 5 minutes
TIME_WINDOW = 300     # 5 minutes in seconds

# Store user XP and activity data
user_xp = defaultdict(int)
user_activity = defaultdict(list)
boost_active = defaultdict(bool)
boost_end_time = defaultdict(float)
boost_cooldown = defaultdict(float)

# Regular expression to detect emojis (anything between `:` symbols)
EMOJI_REGEX = r":([^:]+):"

# Check for activity burst every 2 seconds
@tasks.loop(seconds=2)
async def check_activity_burst():
    current_time = time.time()
    
    for user_id, activities in user_activity.items():
        # Check if the user has exceeded the message limit
        messages_in_time_window = [activity for activity in activities if current_time - activity < TIME_WINDOW]
        
        # Update the activity list to only include recent messages
        user_activity[user_id] = messages_in_time_window
        
        # Check if the user triggered a burst
        if len(messages_in_time_window) >= MESSAGE_LIMIT:
            if not boost_active[user_id] and current_time - boost_cooldown[user_id] >= BOOST_COOLDOWN:
                # Activate boost for the user
                boost_active[user_id] = True
                boost_end_time[user_id] = current_time + BOOST_DURATION
                # Apply the boost (For simplicity, let's just print it for now)
                print(f"XP boost activated for user {user_id}")
                
                # Log the boost activation
                log(f"XP boost activated for user {user_id}")
        
        # Handle boost expiration
        if boost_active[user_id] and current_time >= boost_end_time[user_id]:
            boost_active[user_id] = False
            # Reset the cooldown time after the boost
            boost_cooldown[user_id] = current_time
            print(f"XP boost expired for user {user_id}")
            log(f"XP boost expired for user {user_id}")

# Start the activity burst checking loop
@bot.event
async def on_ready():
    check_activity_burst.start()

# Function to log messages to the general log channel
def log(message):
    """Send log messages to the general log channel."""
    channel = bot.get_channel(GENERAL_LOG_CHANNEL_ID)
    asyncio.create_task(channel.send(message))

# Function to track message activity for bursts
@bot.event
async def on_message(message):
    if message.author == bot.user:  # Ignore the bot's own messages
        return

    user_id = message.author.id
    current_time = time.time()

    # Filter out URLs and non-alphanumeric characters (except spaces)
    filtered_content = re.sub(URL_REGEX, "", message.content)  # Remove URLs
    filtered_content = ''.join(c for c in filtered_content if c.isalnum() or c.isspace())  # Remove non-alphanumeric characters (except spaces)

    # Calculate character XP (1 XP for each alphanumeric character in the filtered content)
    character_xp = len(filtered_content.replace(" ", ""))  # Ignore spaces in XP calculation

    # Calculate emoji XP (5 XP for each emoji found between colons `:`)
    emoji_xp = len(re.findall(EMOJI_REGEX, message.content)) * 5

    # Calculate total XP for this message
    total_xp = character_xp + emoji_xp

    # Add XP to the user's total
    user_xp[user_id] += total_xp

    # Track activity for burst calculation
    user_activity[user_id].append(current_time)

    # Handle message (you can also add more logic here, e.g., response to commands)
    await bot.process_commands(message)

# Define the roles and their corresponding messages
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

@bot.event
async def on_member_update(before, after):
    """Monitor role changes and announce promotions."""
    if before.roles != after.roles:
        for role in after.roles:
            if role.name in ROLE_NAMES and role.name not in [r.name for r in before.roles]:
                await announce_role_update(after, role.name)

async def announce_role_update(member, role_name):
    """Announce role assignment and permission changes."""
    role_info = ROLE_NAMES[role_name]
    message = role_info["message"]
    log_channel = bot.get_channel(ROLE_LOG_CHANNEL_ID)
    await log_channel.send(message.format(member=member))
    log(f"Role {role_name} assigned to {member} at {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}")
    save_data()

def log(message):
    """Send log messages to the general log channel."""
    channel = bot.get_channel(GENERAL_LOG_CHANNEL_ID)
    asyncio.create_task(channel.send(message))

def save_data():
    """Save XP and activity data to a file (optional)."""
    with open("xp_data.json", "w") as f:
        json.dump(user_xp, f)

# Run the bot
bot.run(TOKEN)
