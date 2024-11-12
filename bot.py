import discord
from discord.ext import commands, tasks
import re
import os
import logging
import emoji  # Required for Unicode emoji detection
from emoji import is_emoji
from db_server import (
    update_user_xp,
    track_activity,
    check_boost_cooldown,
    update_boost_cooldown,
    check_activity_burst
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load token from environment variable for security
TOKEN = process.env.DISCORD_BOT_TOKEN;
if not TOKEN:
    logger.error("Bot token not found. Set the DISCORD_BOT_TOKEN environment variable.")
    exit(1)

# Channel IDs (replace with actual IDs)
ROLE_LOG_CHANNEL_ID = 1251143629943345204
LEADERBOARD_CHANNEL_ID = 1301183910838796460

# Define intents
intents = discord.Intents.default()
intents.members = True

# Bot setup
bot = commands.Bot(command_prefix="!", intents=intents)

# Constants for XP boost and activity burst
BOOST_DURATION = 300  # 5 minutes in seconds
BOOST_COOLDOWN = 300  # 5 minutes in seconds
MESSAGE_LIMIT = 10
TIME_WINDOW = 300  # 5-minute window for burst

# Regular expressions
URL_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"

# Placeholder for the leaderboard message
leaderboard_message = None

@bot.event
async def on_ready():
    logger.info(f"Bot logged in as {bot.user.name}")
    update_leaderboard.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id

    # Remove URLs
    filtered_content = re.sub(URL_REGEX, "", message.content)

    # Remove non-alphanumeric characters except spaces
    filtered_content = ''.join(c for c in filtered_content if c.isalnum() or c.isspace())

    # XP Calculation
    character_xp = len(filtered_content.replace(" ", "")) * 0.1

    # Custom emojis
    custom_emoji_count = count_custom_emojis(message.content)

    # Unicode emojis
    unicode_emoji_count = sum(1 for c in message.content if c in is_emoji)

    # Total XP
    emoji_xp = (custom_emoji_count + unicode_emoji_count) * 0.5
    total_xp = character_xp + emoji_xp

    # Update user data
    update_user_xp(user_id, total_xp)
    track_activity(user_id)

    # Activity burst check
    check_activity_burst(user_id)

    await bot.process_commands(message)

def fetch_top_users():
    # Fetch top users from database (adjust for your DB implementation)
    from db_server import cursor
    cursor.execute("SELECT user_id, xp FROM user_xp ORDER BY xp DESC LIMIT 10")
    return cursor.fetchall()

async def get_user_data(user_id):
    user = await bot.fetch_user(user_id)
    return user.display_name, str(user.avatar.url)

async def create_leaderboard_embed(top_users):
    embed = discord.Embed(
        title="🏆 Daily Leaderboard",
        description="Top 10 users of the day:",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Leaderboard refreshes every 15 seconds")

    for rank, (user_id, xp) in enumerate(top_users, 1):
        nickname, avatar_url = await get_user_data(user_id)
        embed.add_field(
            name=f"#{rank} {nickname}",
            value=f"XP: {xp}",
            inline=False
        )
        if rank == 1:
            embed.set_thumbnail(url=avatar_url)

    return embed

@tasks.loop(seconds=15)
async def update_leaderboard():
    try:
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if not channel:
            logger.error(f"Leaderboard channel not found: {LEADERBOARD_CHANNEL_ID}")
            return

        top_users = fetch_top_users()
        embed = await create_leaderboard_embed(top_users)

        messages = await channel.history(limit=1).flatten()
        if messages:
            await messages[0].edit(embed=embed)
        else:
            await channel.send(embed=embed)

    except discord.HTTPException as e:
        logger.error(f"HTTPException while updating leaderboard: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in update_leaderboard: {e}")

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
