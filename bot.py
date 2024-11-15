# bot.py
import discord
from discord.ext import commands, tasks
import re
import logging
import rollbar
from emoji import is_emoji
from db_server import (
    update_user_xp,
    track_activity,
    check_boost_cooldown,
    update_boost_cooldown,
    check_activity_burst,
)
import asyncio
from PIL import Image, ImageDraw, ImageFont
import aiohttp
from io import BytesIO

# Rollbar initialization
rollbar.init(
    access_token='YOUR_ACCESS_TOKEN',  # Replace with your actual Rollbar token
    environment='testenv',
    code_version='1.0'
)
rollbar.report_message('Rollbar is configured correctly', 'info')

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Constants
ROLE_LOG_CHANNEL_ID = 1251143629943345204
LEADERBOARD_CHANNEL_ID = 1303672077068537916
GUILD_ID = 1227505156220784692  # Replace with your actual guild ID
BOOST_DURATION = 300  # 5 minutes
BOOST_COOLDOWN = 300
MESSAGE_LIMIT = 10
TIME_WINDOW = 300
URL_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"

# Intents and bot setup
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Placeholder for leaderboard message
leaderboard_message = None

# Helper Functions
def count_custom_emojis(content):
    return len(re.findall(r'<a?:\w+:\d+>', content))

def fetch_top_users():
    from db_server import cursor
    cursor.execute("SELECT user_id, xp FROM user_xp ORDER BY xp DESC LIMIT 10")
    return cursor.fetchall()

async def fetch_font(font_url, size=24):
    """Fetch and return font from a URL."""
    async with aiohttp.ClientSession() as session:
        async with session.get(font_url) as response:
            if response.status == 200:
                font_data = BytesIO(await response.read())
                return ImageFont.truetype(font_data, size)
            else:
                logger.error(f"Failed to fetch font from {font_url}: {response.status}")
                raise Exception("Font fetch failed")

async def get_member(user_id):
    """Fetch a guild member and their avatar URL."""
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        logger.error("Guild not found")
        return None

    try:
        member = await guild.fetch_member(user_id)
        nickname = member.nick or member.name
        avatar_url = member.avatar_url_as(format="png")  # Compatible with v1.7.3
        return nickname, avatar_url
    except discord.HTTPException as e:
        logger.error(f"Error fetching member {user_id}: {e}")
        return None

async def create_leaderboard_image(top_users):
    """Generate a leaderboard image with emoji rendering."""
    img = Image.new("RGB", (1000, 600), color='white')
    draw = ImageDraw.Draw(img)

    font = await fetch_font("https://example.com/NotoSans-Regular.ttf", size=24)
    emoji_font = await fetch_font("https://example.com/NotoColorEmoji.ttf", size=24)

    y_position = 10

    for rank, (user_id, xp) in enumerate(top_users, 1):
        member_data = await get_member(user_id)
        if not member_data:
            continue

        nickname, avatar_url = member_data

        # Fetch avatar
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as response:
                avatar = Image.open(BytesIO(await response.read())).resize((50, 50))

        img.paste(avatar, (10, y_position))

        # Draw text including nickname and XP
        draw.text((70, y_position), f"#{rank} {nickname} | XP: {int(xp)}", font=font, fill="black")
        y_position += 60

    img_binary = BytesIO()
    img.save(img_binary, format="PNG")
    img_binary.seek(0)
    return img_binary

# Event Handlers
@bot.event
async def on_ready():
    logger.info(f"Bot logged in as {bot.user.name}")
    update_leaderboard.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id
    filtered_content = re.sub(URL_REGEX, "", message.content)
    filtered_content = ''.join(c for c in filtered_content if c.isalnum() or c.isspace())

    character_xp = len(filtered_content.replace(" ", "")) * 0.1
    emoji_xp = (count_custom_emojis(message.content) + sum(1 for c in message.content if is_emoji(c))) * 0.5
    total_xp = character_xp + emoji_xp

    update_user_xp(user_id, total_xp)
    track_activity(user_id)
    check_activity_burst(user_id)
    await bot.process_commands(message)

@tasks.loop(seconds=20)
async def update_leaderboard():
    """Update the leaderboard periodically."""
    try:
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if not channel:
            logger.error("Leaderboard channel not found")
            return

        top_users = fetch_top_users()
        image = await create_leaderboard_image(top_users)

        global leaderboard_message
        if leaderboard_message:
            await leaderboard_message.delete()

        leaderboard_message = await channel.send(file=discord.File(image, filename="leaderboard.png"))
    except Exception as e:
        logger.error(f"Error updating leaderboard: {e}")

# Run the bot
bot.run('MTMwMzQyNjkzMzU4MDc2MzIzNg.GpSZcY.4mvu2PTpCOm7EuCaUecADGgssPLpxMBrlHjzbI')  # Replace with your actual bot token
