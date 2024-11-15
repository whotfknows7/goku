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
            # Fetch the guild using the correct method
            guild = bot.get_guild(GUILD_ID)

            if not guild:
                logger.error(f"Guild with ID {GUILD_ID} not found")
                return None

            # Use the guild to fetch the member
            member = await guild.fetch_member(user_id)

            nickname = member.nick if member.nick else member.name
            avatar_url = member.avatar_url if member.avatar_url else None

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

    # Render leaderboard
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
        x_position_rank = PADDING + 55  # Position the rank to the right of the PFP

        # Draw rank in the center of the PFP and nickname area
        draw.text((x_position_rank, y_position), rank_text, font=font, fill="black")

        # Position nickname and separator '|'
        x_position = x_position_rank + rank_width + 10  # Add a little padding after rank
        separator = " | "
        draw.text((x_position, y_position), separator, font=font, fill="black")
        x_position += draw.textbbox((x_position, y_position), separator, font=font)[2] - draw.textbbox((x_position, y_position), separator, font=font)[0]  # Move x_position after separator

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
        x_position += 10  # Extra padding for the points
        draw.text((x_position, y_position), f"Points: {int(xp)}", font=font, fill="black")

        y_position += 60  # Move to next row for the next user

    img_binary = BytesIO()
    img.save(img_binary, format="PNG")
    img_binary.seek(0)

    return img_binary

@tasks.loop(seconds=20)
async def update_leaderboard():
    try:
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)

        if not channel:
            logger.error(f"Leaderboard channel not found: {LEADERBOARD_CHANNEL_ID}")
            return

        # Fetch the leaderboard data
        top_users = fetch_top_users()

        # Generate the leaderboard image
        image = await create_leaderboard_image(top_users)

        # Ensure image is passed as a file, not trying to log or serialize the object
        global leaderboard_message

        if leaderboard_message:
            # Delete the previous message if it exists
            await leaderboard_message.delete()

        # Send the new leaderboard message from scratch
        leaderboard_message = await channel.send(file=discord.File(image, filename="leaderboard.png"))

    except discord.HTTPException as e:
        if e.status == 429:
            retry_after = int(e.retry_after)
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

bot.run('MTMwMzQyNjkzMzU4MDc2MzIzNg.GpSZcY.4mvu2PTpCOm7EuCaUecADGgssPLpxMBrlHjzbI')  # Replace with
