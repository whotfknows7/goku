import discord
from discord.ext import commands, tasks
import re
import time
import os
import sqlite3
import logging
# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
# Import functions from db_server.py
from db_server import update_user_xp, track_activity, check_boost_cooldown, update_boost_cooldown, check_activity_burst

TOKEN = 'MTMwMzQyNjkzMzU4MDc2MzIzNg.GKuML2.ui6KSSwq0dL-v2DWk3aYtPsCvPYm1WgFzBiFTM'
ROLE_LOG_CHANNEL_ID = 1251143629943345204  # Replace with your role log channel ID
GENERAL_LOG_CHANNEL_ID = 1301183910838796460  # Replace with your general log channel ID
LEADERBOARD_CHANNEL_ID = 123456789012345678  # Replace with your log channel ID
# Define intents
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
# Rank color mapping (background color & name color)
RANK_COLORS = [
    ("#FFD700", "#DC143C"),  # Rank 1: Gold & Crimson
    ("#C0C0C0", "#FF8C00"),  # Rank 2: Silver & DarkOrange
    ("#CD7F32", "#DA70D6"),  # Rank 3: Bronze & Orchid
    ("#8B008B", "#7FFF00"),  # Rank 4: DarkMagenta & Chartreuse
    ("#00BFFF", "#FF6347"),  # Rank 5: DeepSkyBlue & Tomato
    ("#BDB76B", "#20B2AA"),  # Rank 6: DarkKhaki & LightSeaGreen
    ("#4682B4", "#CD853F"),  # Rank 7: SteelBlue & Peru
    ("#708090", "#00CED1"),  # Rank 8: SlateGray & DarkTurquoise
    ("#66CDAA", "#DAA520"),  # Rank 9: MediumAquamarine & GoldenRod
    ("#696969", "#B0C4DE"),  # Rank 10: DimGray & LightSteelBlue
]
# Placeholder for the leaderboard message
leaderboard_message = None

# Constants for XP boost and activity burst
BOOST_DURATION = 300  # 5 minutes in seconds
BOOST_COOLDOWN = 300  # 5 minutes in seconds
MESSAGE_LIMIT = 10
TIME_WINDOW = 300  # 5-minute window for burst

# Regular expressions
URL_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
EMOJI_REGEX = r":([^:]+):"

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.event
async def on_message(message):
    # Skip processing if the message is sent by a bot
    if message.author.bot:
        return

    user = message.author
    user_id = message.author.id
    filtered_content = re.sub(URL_REGEX, "", message.content)
    filtered_content = ''.join(c for c in filtered_content if c.isalnum() or c.isspace())

    # Calculate XP
    character_xp = len(filtered_content.replace(" ", "")) * 0.1
    emoji_xp = len(re.findall(EMOJI_REGEX, message.content)) * 0.5
    total_xp = character_xp + emoji_xp

    # Update XP in the database
    update_user_xp(user_id, total_xp)
    track_activity(user_id)

    # Check for activity burst and apply XP boost if applicable
    check_activity_burst(user_id, message)  # Call it without 'await'

    # Allow commands to be processed after custom logic
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
