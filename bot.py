import discord
from discord.ext import commands, tasks
import re
import logging
import rollbar
import rollbar.contrib.flask
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
from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests
from io import BytesIO

# Rollbar initialization
rollbar.init(
    access_token='cfd2554cc40741fca49e3d8d6502f039',
    environment='testenv',
    code_version='1.0'
)
rollbar.report_message('Rollbar is configured correctly', 'info')


# Channel IDs
ROLE_LOG_CHANNEL_ID = 1251143629943345204
LEADERBOARD_CHANNEL_ID = 1303672077068537916

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

# Function to count custom emojis in a message
def count_custom_emojis(content):
    custom_emoji_pattern = r'<a?:\w+:\d+>'
    return len(re.findall(custom_emoji_pattern, content))

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
                # If rate-limited, get the retry time
                retry_after = float(e.response.headers.get('X-RateLimit-Reset', time.time()))
                wait_time = retry_after - time.time()
                if wait_time > 0:
                    logger.warning(f"Rate-limited. Retrying after {wait_time:.2f} seconds.")
                    await asyncio.sleep(wait_time)
            else:
                raise e
    return None, None  # In case of error, return None

async def create_leaderboard_image(top_users):
    WIDTH, HEIGHT = 1000, 600
    PADDING = 20
    PFP_SIZE = 80  # Match PFP size to the sample image
    LINE_SPACING = 20

    img = Image.new('RGB', (WIDTH, HEIGHT), color='white')
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    y_position = PADDING

    for rank, (user_id, xp) in enumerate(top_users, 1):
        nickname, avatar_url = await get_user_data(user_id)

        # Fetch and resize PFP
        response = requests.get(avatar_url)
        img_pfp = Image.open(BytesIO(response.content)).resize((PFP_SIZE, PFP_SIZE))
        img.paste(img_pfp, (PADDING, y_position))

        # Text formatting
        text_sample = f"#{rank} {nickname} - Points: {int(xp)}"
        text_x = PADDING + PFP_SIZE + 10  # Text beside PFP
        text_y = y_position + (PFP_SIZE - draw.textbbox((0, 0), text_sample, font=font)[3]) // 2

        draw.text((text_x, text_y), text_sample, font=font, fill="black")

        # Move to next row
        y_position += PFP_SIZE + LINE_SPACING

    img_cropped = img.crop((0, 0, WIDTH, y_position + PADDING))

    with BytesIO() as img_binary:
        img_cropped.save(img_binary, format='PNG')
        img_binary.seek(0)
        return img_binary
@tasks.loop(seconds=20)
async def update_leaderboard():
    global leaderboard_message  # Declare global to modify the message variable
    try:
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if not channel:
            logger.error(f"Leaderboard channel not found: {LEADERBOARD_CHANNEL_ID}")
            return

        top_users = fetch_top_users()
        image = await create_leaderboard_image(top_users)

        if leaderboard_message is None:
            leaderboard_message = await channel.send(
                content="Here is the updated leaderboard!",
                file=discord.File(fp=image, filename="leaderboard.png")
            )
        else:
            await leaderboard_message.delete()
            leaderboard_message = await channel.send(
                content="Here is the updated leaderboard!",
                file=discord.File(fp=image, filename="leaderboard.png")
            )

    except discord.HTTPException as e:
        if e.status == 429:
            retry_after = int(e.response.headers.get('X-RateLimit-Reset', time.time()))
            logger.warning(f"Rate-limited. Retrying after {retry_after} seconds.")
            await asyncio.sleep(retry_after)
        else:
            logger.error(f"HTTPException while updating leaderboard: {e}")

    except Exception as e:
        logger.error(f"Unexpected error in update_leaderboard: {e}")

# Role update handling
ROLE_NAMES = {
    "🧔Homo Sapien": {"message": "🎉 Congrats {member.mention}! You've become a **Homo Sapien** 🧔 and unlocked GIF permissions!", "has_perms": True},
    "🏆Homie": {"message": "🎉 Congrats {member.mention}! You've become a **Homie** 🏆 and unlocked Image permissions!", "has_perms": True},
    "🥉VETERAN": {"message": "🎉 Congrats {member.mention}! You've become a **VETERAN** 🥉 member!", "has_perms": False},
    "🥈ELITE": {"message": "🎉 Congrats {member.mention}! You've become an **ELITE** 🥈 member!", "has_perms": False},
    "🥇MYTHIC": {"message": "🎉 Congrats {member.mention}! You've become a **MYTHIC** 🥇 member!", "has_perms": False},
    "⭐VIP": {"message": "🎉 Congrats {member.mention}! You've become a **VIP** ⭐ member!", "has_perms": False},
    "✨LEGENDARY": {"message": "🎉 Congrats {member.mention}! You've become a **LEGENDARY** ✨ member!", "has_perms": False},
}

# Event when member's roles update
@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        for role in after.roles:
            if role.name in ROLE_NAMES and role.name not in [r.name for r in before.roles]:
                await announce_role_update(after, role.name)

# Announce role update
async def announce_role_update(member, role_name):
    role_info = ROLE_NAMES.get(role_name)
    if role_info:
        message = role_info["message"].format(member=member)
        channel = bot.get_channel(ROLE_LOG_CHANNEL_ID)
        await channel.send(message)

# Run bot with token
bot.run('MTMwMzQyNjkzMzU4MDc2MzIzNg.GSHne3.vXMfND2Ua3qErwZI4JSaEfLTsN3fXSyTrfJPgk')  # Replace with
