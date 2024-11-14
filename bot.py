import discord
from discord.ext import commands, tasks
import re
import logging
from emoji import is_emoji
from db_server import (
    update_user_xp,
    track_activity,
    check_activity_burst,
)
import asyncio
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import time
import rollbar
# Rollbar initialization
rollbar.init(
    access_token='your_rollbar_access_token',
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

# Bot setup
bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

# Constants
BOOST_DURATION = 300  # 5 minutes in seconds
BOOST_COOLDOWN = 300  # 5 minutes in seconds

# Regular expressions
URL_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"

# Placeholder for the leaderboard message
leaderboard_message = None

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

# Async function to get user data with rate-limiting handling
async def get_user_data(user_id):
    retry_after = 0
    while retry_after == 0:
        try:
            user = await bot.fetch_user(user_id)
            display_name = user.display_name
            avatar_url = user.avatar_url if user.avatar else None
            return display_name, avatar_url
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = float(e.response.headers.get('X-RateLimit-Reset', time.time()))
                wait_time = retry_after - time.time()
                if wait_time > 0:
                    logger.warning(f"Rate-limited. Retrying after {wait_time:.2f} seconds.")
                    await asyncio.sleep(wait_time)
            else:
                raise e
    return None, None

# Create leaderboard GIF
async def create_leaderboard_gif(top_users):
    # Image size and padding
    WIDTH, HEIGHT = 1000, 600
    PADDING = 10
    frames = []

    # Font
    font = ImageFont.load_default()

    # Loop through the top users to create frames
    for frame_num in range(5):  # Create 5 frames for example (this can be adjusted)
        img = Image.new('RGB', (WIDTH, HEIGHT), color='white')
        draw = ImageDraw.Draw(img)

        # Initial position for the leaderboard content
        y_position = PADDING

        # Loop through the top users to add their info to the image
        for rank, (user_id, xp) in enumerate(top_users, 1):
            nickname, avatar_url = await get_user_data(user_id)

            # Fetch user profile picture (resize it for the image)
            response = requests.get(avatar_url)
            img_pfp = Image.open(BytesIO(response.content))
            img_pfp = img_pfp.resize((50, 50))  # Resize to 50x50 pixels

            # Draw the profile picture (left-aligned)
            img.paste(img_pfp, (PADDING, y_position))

            # Draw the rank, nickname, and points
            draw.text((PADDING + 60, y_position), f"#{rank} {nickname}", font=font, fill="black")
            draw.text((PADDING + 200, y_position), f"Points: {int(xp)}", font=font, fill="black")

            # Move to the next row
            y_position += 60  # Adjust space between rows

        # Add the frame to the list of frames
        frames.append(img)

    # Save the frames as a GIF
    gif_path = "leaderboard.gif"
    frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=500, loop=0)

    return gif_path

# Task to update the leaderboard
@tasks.loop(seconds=20)
async def update_leaderboard():
    try:
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if not channel:
            logger.error(f"Leaderboard channel not found: {LEADERBOARD_CHANNEL_ID}")
            return

        # Fetch the leaderboard data
        top_users = fetch_top_users()

        # Generate the leaderboard GIF
        gif_path = await create_leaderboard_gif(top_users)

        # Send the GIF as an attachment
        await channel.send(file=discord.File(gif_path))

    except discord.HTTPException as e:
        if e.status == 429:
            retry_after = int(e.retry_after)
            logger.warning(f"Rate-limited. Retrying after {retry_after} seconds.")
            await asyncio.sleep(retry_after)
        else:
            logger.error(f"HTTPException while updating leaderboard: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in update_leaderboard: {e}")

# Run bot with token
bot.run('MTMwMzQyNjkzMzU4MDc2MzIzNg.GSHne3.vXMfND2Ua3qErwZI4JSaEfLTsN3fXSyTrfJPgk')  # Replace with your bot token
