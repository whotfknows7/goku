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
    check_activity_burst
)
import asyncio
import time
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO

# Rollbar initialization
rollbar.init(
    access_token='cfd2554cc40741fca49e3d8d6502f039',
    environment='testenv',
    code_version='1.0'
)
rollbar.report_message('Rollbar is configured correctly', 'info')

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Channel IDs
ROLE_LOG_CHANNEL_ID = 1251143629943345204
LEADERBOARD_CHANNEL_ID = 1303672077068537916
GUILD_ID = 1227505156220784692  # Replace with your actual guild ID

# Define intents
intents = discord.Intents.default()
intents.members = True

# Bot setup
bot = commands.Bot(command_prefix="!", intents=intents)

# Constants
BOOST_DURATION = 300  # 5 minutes in seconds
BOOST_COOLDOWN = 300  # 5 minutes in seconds
MESSAGE_LIMIT = 10
TIME_WINDOW = 300  # 5-minute window for burst

# Regular expressions
URL_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"

# Placeholder for the leaderboard message
leaderboard_message = None
image_cache = None

# Function to count custom emojis in a message
def count_custom_emojis(content):
    custom_emoji_pattern = r'<a?:\w+:\d+>'
    return len(re.findall(custom_emoji_pattern, content))

# Bot event when ready
@bot.event
async def on_ready():
    logger.info(f"Bot logged in as {bot.user.name}")
    update_leaderboard.start()

# Bot event for incoming messages
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id
    # Remove URLs and non-alphanumeric characters except spaces
    filtered_content = re.sub(URL_REGEX, "", message.content)
    filtered_content = ''.join(c for c in filtered_content if c.isalnum() or c.isspace())

    # XP Calculation
    character_xp = len(filtered_content.replace(" ", "")) * 0.1
    custom_emoji_count = count_custom_emojis(message.content)
    unicode_emoji_count = sum(1 for c in message.content if is_emoji(c))
    emoji_xp = (custom_emoji_count + unicode_emoji_count) * 0.5
    total_xp = character_xp + emoji_xp

    # Update user data
    update_user_xp(user_id, total_xp)
    track_activity(user_id)

    # Activity burst check
    check_activity_burst(user_id)

    await bot.process_commands(message)

# Fetch top users for leaderboard
def fetch_top_users():
    from db_server import cursor
    cursor.execute("SELECT user_id, xp FROM user_xp ORDER BY xp DESC LIMIT 10")
    return cursor.fetchall()

async def get_member(user_id):
    retry_after = 0
    while retry_after == 0:
        try:
            guild = bot.get_guild(GUILD_ID)
            if not guild:
                logger.error(f"Guild with ID {GUILD_ID} not found")
                return None

            member = await guild.fetch_member(user_id)
            nickname = member.nick if member.nick else member.name
            avatar_url = member.avatar.url if member.avatar else None

            return nickname, avatar_url
        except discord.HTTPException as e:
            if e.status == 429:  # Rate-limited
                retry_after = float(e.response.headers.get('X-RateLimit-Reset', time.time()))
                wait_time = retry_after - time.time()
                if wait_time > 0:
                    logger.warning(f"Rate-limited. Retrying after {wait_time:.2f} seconds.")
                    await asyncio.sleep(wait_time)
                else:
                    raise
            else:
                logger.error(f"Failed to fetch member {user_id} in guild {GUILD_ID}: {e}")
                return None

async def create_leaderboard_image(top_users):
    WIDTH, HEIGHT = 1000, 600
    PADDING = 10

    img = Image.new("RGB", (WIDTH, HEIGHT), color='white')
    draw = ImageDraw.Draw(img)

    # Fetch fonts
    font_url = "https://github.com/whotfknows7/noto_sans/raw/refs/heads/main/NotoSans-VariableFont_wdth,wght.ttf"
    response = requests.get(font_url)
    font_data = BytesIO(response.content)
    font = ImageFont.truetype(font_data, size=24)

    emoji_font_url = "https://github.com/whotfknows7/idk-man/raw/refs/heads/main/NotoColorEmoji-Regular.ttf"
    response = requests.get(emoji_font_url)
    font_data = BytesIO(response.content)
    emoji_font = ImageFont.truetype(font_data, size=24)

    y_position = PADDING

    for rank, (user_id, xp) in enumerate(top_users, 1):
        member = await get_member(user_id)
        if not member:
            continue

        nickname, avatar_url = member

        # Fetch user profile picture
        try:
            response = requests.get(avatar_url)
            img_pfp = Image.open(BytesIO(response.content))
            img_pfp = img_pfp.resize((50, 50))
        except Exception as e:
            logger.error(f"Failed to fetch avatar for user {user_id}: {e}")
            img_pfp = Image.new('RGB', (50, 50), color='grey')

        img.paste(img_pfp, (PADDING, y_position))

        # Draw rank and nickname with appropriate font (handling emojis)
        rank_text = f"#{rank}"
        rank_bbox = draw.textbbox((0, 0), rank_text, font=font)
        rank_width = rank_bbox[2] - rank_bbox[0]

        # Draw rank in the center of the PFP and nickname area
        x_position_rank = PADDING + 60  # Position the rank to the right of the PFP
        draw.text((x_position_rank, y_position), rank_text, font=font, fill="black")

        # Position nickname and separator '|'
        x_position = x_position_rank + rank_width + 3  # Reduced padding after rank
        separator = " | "
        draw.text((x_position, y_position), separator, font=font, fill="black")
        
        # Move x_position after separator
        separator_width = draw.textbbox((x_position, y_position), separator, font=font)[2] - draw.textbbox((x_position, y_position), separator, font=font)[0]
        x_position += separator_width

        # Render nickname (handling emojis)
        for char in nickname:
            if is_emoji(char):
                draw.text((x_position, y_position), char, font=emoji_font, fill="black")
                bbox = draw.textbbox((x_position, y_position), char, font=emoji_font)
                char_width = bbox[2] - bbox[0]
                x_position += char_width
            else:
                draw.text((x_position, y_position), char, font=font, fill="black")
                bbox = draw.textbbox((x_position, y_position), char, font=font)
                char_width = bbox[2] - bbox[0]
                x_position += char_width

        # Position and render the points
        x_position += 5  # Reduced extra padding for the points
        points_text = f" | PTS: {int(xp)}"
        draw.text((x_position, y_position), points_text, font=font, fill="black")

        y_position += 60  # Move to next row for the next user

    img_binary = BytesIO()
    img.save(img_binary, format="PNG")
    img_binary.seek(0)

    return img_binary

@tasks.loop(seconds=32)
async def update_leaderboard():
    global image_cache
    try:
        # Start generating image at the 20th second
        asyncio.create_task(pre_generate_image())

        await asyncio.sleep(12)  # Wait to align with 32s mark.

        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if not channel:
            logger.error(f"Leaderboard channel not found: {LEADERBOARD_CHANNEL_ID}")
            return

        if leaderboard_message:
            # Delete the previous message if it exists
            await leaderboard_message.delete()
        
        # Send the new leaderboard message from scratch
        leaderboard_message = await channel.send(file=discord.File(image_cache, filename="leaderboard.png"))

    except Exception as e:
        logger.error(f"Unexpected error in update_leaderboard: {e}")

async def pre_generate_image():
    try:
        # Refresh data
        top_users = fetch_top_users()
        image_cache = await create_leaderboard_image(top_users)  # Pre-cache the image
        
    except Exception as e:
        logger.error(f"Failed to generate leaderboard image: {e}")

bot.run('MTMwMzQyNjkzMzU4MDc2MzIzNg.GpSZcY.4mvu2PTpCOm7EuCaUecADGgssPLpxMBrlHjzbI')
