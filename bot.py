import discord
from discord.ext import tasks, commands
import sqlite3
import os
import logging
import re

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Bot configuration
TOKEN = MTMwMzQyNjkzMzU4MDc2MzIzNg.Gfa6na.X21jZAdDaiNStwNJK3TId7qWWZrbuGdBlAKA7Q'
LEADERBOARD_CHANNEL_ID = 1301183910838796460  # Replace with your leaderboard channel ID
ROLE_LOG_CHANNEL_ID = 1251143629943345204   # Replace with your role log channel ID
GENERAL_LOG_CHANNEL_ID = 1301183910838796460  # General log channel

# Define intents
intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Constants for XP boost, activity burst, and rank colors
BOOST_DURATION = 300
BOOST_COOLDOWN = 300
MESSAGE_LIMIT = 10
TIME_WINDOW = 300
URL_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\,]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
EMOJI_REGEX = r":([^:]+):"
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

# Placeholder for leaderboard message
leaderboard_message = None

# Role configurations for role updates
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

# Fetch leaderboard data from the database
def fetch_leaderboard_data():
    try:
        conn = sqlite3.connect('leaderboard.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, points
            FROM daily_leaderboard
            ORDER BY points DESC
            LIMIT 10;
        """)
        data = cursor.fetchall()
        conn.close()
        return data
    except sqlite3.Error as e:
        logger.error(f"SQLite error: {e}")
        return []

# Update leaderboard message periodically
@tasks.loop(seconds=15)
async def update_leaderboard():
    global leaderboard_message
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    leaderboard_data = fetch_leaderboard_data()

    if not leaderboard_data:
        logger.error("No leaderboard data found.")
        return

    embed = discord.Embed(title="🏆 Live Leaderboard", description="Tracking the top players!", color=discord.Color.green())
    for rank, (user_id, points) in enumerate(leaderboard_data[:10], start=1):
        user = await bot.fetch_user(user_id)
        background_color, _ = RANK_COLORS[rank - 1] if rank - 1 < len(RANK_COLORS) else ("#32CD32", "#000000")
        embed.add_field(name=f"{rank}. {user.display_name}", value=f"Points: {points}", inline=False)
        embed.color = discord.Color.from_str(background_color)

    try:
        if leaderboard_message:
            await leaderboard_message.edit(embed=embed)
        else:
            leaderboard_message = await channel.send(embed=embed)
    except discord.DiscordException as e:
        logger.error(f"Failed to update leaderboard message: {e}")

# Calculate points change based on message content
def calculate_points_change(message):
    filtered_content = re.sub(URL_REGEX, "", message.content)
    filtered_content = ''.join(c for c in filtered_content if c.isalnum() or c.isspace())
    character_xp = len(filtered_content.replace(" ", "")) * 0.1
    emoji_xp = len(re.findall(EMOJI_REGEX, message.content)) * 0.5
    return character_xp + emoji_xp

# Update user's points in the database
def update_user_points(user_id, points_change):
    try:
        conn = sqlite3.connect('leaderboard.db')
        cursor = conn.cursor()
        cursor.execute("SELECT points FROM daily_leaderboard WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            cursor.execute("UPDATE daily_leaderboard SET points = points + ? WHERE user_id = ?", (points_change, user_id))
        else:
            cursor.execute("INSERT INTO daily_leaderboard (user_id, points) VALUES (?, ?)", (user_id, points_change))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"SQLite error while updating points: {e}")

# Announce role updates
async def announce_role_update(member, role_name):
    role_info = ROLE_NAMES.get(role_name)
    if role_info:
        message = role_info["message"].format(member=member)
        channel = bot.get_channel(ROLE_LOG_CHANNEL_ID)
        await channel.send(message)

# Events
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    update_leaderboard.start()  # Start leaderboard updates

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id
    points_change = calculate_points_change(message)
    if points_change > 0:
        update_user_points(user_id, points_change)
        logger.info(f"Updated points for {message.author.display_name}: +{points_change} points.")

    await bot.process_commands(message)

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        for role in after.roles:
            if role.name in ROLE_NAMES and role.name not in [r.name for r in before.roles]:
                await announce_role_update(after, role.name)

bot.run(TOKEN)