import discord
from discord.ext import commands, tasks
import re
import time
import os
# Import functions from db_server.py
from db_server import update_user_xp, track_activity, check_boost_cooldown, update_boost_cooldown, check_activity_burst

TOKEN = 'MTMwMzQyNjkzMzU4MDc2MzIzNg.GBNjfR.0TLNjKIh17zO07WFZsIhGu6xbY_kemLvxvFZvI'
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
TIME_WINDOW = 300  # 5-minute window for burst

# Regular expressions
URL_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
EMOJI_REGEX = r":([^:]+):"

# Function to update user XP in the database
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    user_id = message.author.id
    filtered_content = re.sub(URL_REGEX, "", message.content)
    filtered_content = ''.join(c for c in filtered_content if c.isalnum() or c.isspace())

    character_xp = len(filtered_content.replace(" ", "")) * 0.1
    emoji_xp = len(re.findall(EMOJI_REGEX, message.content)) * 0.5
    total_xp = character_xp + emoji_xp

    # Call the functions from db_server.py for database operations
    update_user_xp(user_id, total_xp)
    track_activity(user_id)

    # Check for activity burst and apply XP boost if applicable
    await check_activity_burst(user_id, message)
    
    await bot.process_commands(message)

ROLE_NAMES = {
    "🧔Homo Sapien": {
        "message": "🎉 Congrats {member.mention}! You've become a **Homo Sapien** 🧔 and unlocked GIF permissions!",
        "has_perms": True
    },
    "🏆Homie": {
        "message": "🎉 Congrats {member.mention}! You've become a **Homie** 🏆 and unlocked Image permissions!",
        "has_perms": True
    },
    "🥉VETERAN": {
        "message": "🎉 Congrats {member.mention}! You've become a **VETERAN** 🥉 member!",
        "has_perms": False
    },
    "🥈ELITE": {
        "message": "🎉 Congrats {member.mention}! You've become an **ELITE** 🥈 member!",
        "has_perms": False
    },
    "🥇MYTHIC": {
        "message": "🎉 Congrats {member.mention}! You've become a **MYTHIC** 🥇 member!",
        "has_perms": False
    },
    "⭐VIP": {
        "message": "🎉 Congrats {member.mention}! You've become a **VIP** ⭐ member!",
        "has_perms": False
    },
    "✨LEGENDARY": {
        "message": "🎉 Congrats {member.mention}! You've become a **LEGENDARY** ✨ member!",
        "has_perms": False
    },
}


@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        for role in after.roles:
            if role.name in ROLE_NAMES and role.name not in [r.name for r in before.roles]:
                await announce_role_update(after, role.name)

async def announce_role_update(member, role_name):
    role_info = ROLE_NAMES.get(role_name)
    if role_info:
        message = role_info["message"].format(member=member)
        channel = bot.get_channel(ROLE_LOG_CHANNEL_ID)
        await channel.send(message)

bot.run(TOKEN)
