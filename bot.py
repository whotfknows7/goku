import discord
from discord.ext import commands, tasks
import logging
from emoji import is_emoji  # If you only need `is_emoji`, no need to import `emoji` entirely
import asyncio
import time
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
from io import BytesIO
import os

# Database functions import
from db_server import (
    update_user_xp,
    track_activity,
    check_boost_cooldown,
    update_boost_cooldown,
    check_activity_burst
)

# Error tracking
import rollbar
import rollbar.contrib.flask  # Only if you're using Flask integration

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

# Constants for image dimensions
WIDTH, HEIGHT = 702, 610  # Set image size
PADDING = 10  # Space from the edges of the image


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

# Function to create a rounded mask for profile pictures
def create_rounded_mask(size, radius=10):  # Reduced the radius to 10 for less rounding
    mask = Image.new('L', size, 0)  # 'L' mode creates a grayscale image
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)  # Adjusted radius
    return mask

# Function to round the corners of a profile picture
def round_pfp(img_pfp):
    # Ensure the image is in RGBA mode to support transparency
    img_pfp = img_pfp.convert('RGBA')
    # Create a rounded mask with the size of the image
    mask = create_rounded_mask(img_pfp.size)
    img_pfp.putalpha(mask)  # Apply the rounded mask as alpha (transparency)
    return img_pfp
async def fetch_top_users_with_xp():
    from db_server import cursor
    cursor.execute("SELECT user_id, xp FROM user_xp ORDER BY xp DESC LIMIT 10")
    return cursor.fetchall()

async def get_member(user_id):
    try:
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            logger.error(f"Guild with ID {GUILD_ID} not found")
            return None

        member = await guild.fetch_member(user_id)
        nickname = member.nick if member.nick else member.name
        avatar_url = member.avatar_url if member.avatar_url else None
        return nickname, avatar_url

    except discord.HTTPException as e:
        logger.error(f"Failed to fetch member {user_id} in guild {GUILD_ID}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch member {user_id} in guild {GUILD_ID}: {e}")
        return None

async def create_leaderboard_image():
    img = Image.new("RGBA", (WIDTH, HEIGHT), color=(0, 0, 0, 255))  # Set background color to black
    draw = ImageDraw.Draw(img)

    # Download and load the primary font (TT Fors Trial Bold)
    font_url = "https://cdn.glitch.global/04f6dfef-4255-4a66-b865-c95597b8df08/TT%20Fors%20Trial%20Bold.ttf?v=1731866074399"
    response = requests.get(font_url)

    if response.status_code == 200:
        with open("TT Fors Trial Bold.ttf", "wb") as f:
            f.write(response.content)
        font = ImageFont.truetype("TT Fors Trial Bold.ttf", size=28)
    else:
        logger.error("Failed to download font. Using default font instead.")
        font = ImageFont.load_default()  # Fallback to default font

    # Load the Noto Sans Emoji font (only once)
    emoji_font_path = "NotoColorEmoji.ttf"
    if not os.path.exists(emoji_font_path):
        emoji_font_url = "https://cdn.glitch.me/04f6dfef-4255-4a66-b865-c95597b8df08/NotoColorEmoji-Regular.ttf?v=1731916149427"
        response = requests.get(emoji_font_url)
        if response.status_code == 200:
            with open(emoji_font_path, "wb") as f:
                f.write(response.content)
            print("Noto Sans Emoji font downloaded successfully.")
        else:
            print("Failed to download Noto Sans Emoji font.")
    emoji_font = ImageFont.truetype(emoji_font_path, size=28)

    # Rank-specific background colors
    rank_colors = {
        1: "#FFD700",  # Gold for Rank 1
        2: "#E6E8FA",  # Silver for Rank 2
        3: "#CD7F32",  # Bronze for Rank 3
    }

    y_position = PADDING
    top_users = await fetch_top_users_with_xp()

    if not top_users:
        # If no users fetched, display a message
        draw.text((PADDING, PADDING), "No users found", font=font, fill="white")
    else:
        for rank, (user_id, xp) in enumerate(top_users, 1):
            member = await get_member(user_id)
            if not member:
                continue
            nickname, avatar_url = member

            # Set background color based on rank
            rank_bg_color = rank_colors.get(rank, "#36393e") 

            # Draw the rounded rectangle for the rank
            draw.rounded_rectangle(
                [(PADDING, y_position), (WIDTH - PADDING, y_position + 57)],
                radius=10,  # Adjust radius for corner rounding
                fill=rank_bg_color
            )

            # Fetch user profile picture
            try:
                response = requests.get(avatar_url)
                img_pfp = Image.open(BytesIO(response.content))
                img_pfp = img_pfp.resize((57, 57))  # Resize PFP to 57x57
                img_pfp = round_pfp(img_pfp)  # Apply rounded corners to the PFP
            except Exception as e:
                logger.error(f"Failed to fetch avatar for user {user_id}: {e}")
                img_pfp = Image.new('RGBA', (57, 57), color=(128, 128, 128, 255))  # Default grey circle

            img.paste(img_pfp, (PADDING, y_position), img_pfp)  # Use the alpha mask when pasting

            # Calculate the Y-position for the rank text (centered vertically relative to PFP)
            rank_text = f"#{rank}"
            rank_bbox = draw.textbbox((0, 0), rank_text, font=font)
            rank_height = rank_bbox[3] - rank_bbox[1]  # Height of rank text
            rank_y_position = y_position + (57 - rank_height) // 2 - 5  # Centered with 5px upward offset

            # Render rank with adjusted vertical alignment (centered with PFP) and outline
            draw.text((PADDING + 65, rank_y_position), rank_text, font=font, fill="white", stroke_width=1, stroke_fill="black")

            # Calculate the width of the rank text to position the "|" right after it
            rank_width = rank_bbox[2] - rank_bbox[0]  # Width of rank text

            # Calculate Y-position for the first "|" separator (aligned with rank text)
            first_separator_y_position = rank_y_position  # Keep separator aligned with rank text

            # Render the first "|" separator with outline
            first_separator_text = "|"
            outline_color = "black"
            outline_width = 1

            # Calculate first separator position and text size
            first_separator_position = PADDING + 65 + rank_width + 5
            first_separator_bbox = draw.textbbox((0, 0), first_separator_text, font=font)

            # Draw outline first
            for x_offset in range(-outline_width, outline_width + 1):
                for y_offset in range(-outline_width, outline_width + 1):
                    draw.text((first_separator_position + x_offset, first_separator_y_position + y_offset),
                              first_separator_text, font=font, fill=outline_color)

            # Then draw the separator text
            draw.text((first_separator_position, first_separator_y_position), first_separator_text, font=font, fill="white")

            # Calculate the Y-position for the nickname text (centered vertically relative to PFP)
            nickname_bbox = draw.textbbox((0, 0), nickname, font=font)
            nickname_height = nickname_bbox[3] - nickname_bbox[1]
            nickname_y_position = y_position + (57 - nickname_height) // 2 - 5  # Centered with 5px upward offset

            # Apply emoji font only to nickname if emojis are present
            if any(char in emoji.UNICODE_EMOJI for char in nickname):  # Check for emoji characters
                draw.text((first_separator_position + 20, nickname_y_position), nickname, font=emoji_font, fill="white", stroke_width=1, stroke_fill="black")
            else:
                draw.text((first_separator_position + 20, nickname_y_position), nickname, font=font, fill="white", stroke_width=1, stroke_fill="black")

            # Fetch the width of the nickname text
            nickname_width = nickname_bbox[2] - nickname_bbox[0]  # Calculate width from bbox

            # Calculate Y-position for the second "|" separator (aligned with nickname text)
            second_separator_y_position = nickname_y_position  # Keep separator aligned with nickname text

            # Render the second "|" separator with outline
            second_separator_text = "|"
            second_separator_position = first_separator_position + 20 + nickname_width  # Position after nickname
            second_separator_bbox = draw.textbbox((0, 0), second_separator_text, font=font)

            # Draw outline first
            for x_offset in range(-outline_width, outline_width + 1):
                for y_offset in range(-outline_width, outline_width + 1):
                    draw.text((second_separator_position + x_offset, second_separator_y_position + y_offset),
                              second_separator_text, font=font, fill=outline_color)

            # Then draw the separator text
            draw.text((second_separator_position, second_separator_y_position), second_separator_text, font=font, fill="white")

            # Calculate Y-position for the points (XP) text (centered vertically relative to PFP)
            points_text = f"XP: {int(xp)} Pts"
            points_bbox = draw.textbbox((0, 0), points_text, font=font)
            points_height = points_bbox[3] - points_bbox[1]
            points_y_position = y_position + (57 - points_height) // 2 - 5  # Centered with 5px upward offset

            # Render points (XP) with vertical alignment and outline
            points_position = second_separator_position + 20  # Space between second "|" and points text
            draw.text((points_position, points_y_position), points_text, font=font, fill="white", stroke_width=1, stroke_fill="black")

            y_position += 60  # Space for next row of text

    img_binary = BytesIO()
    img.save(img_binary, format="PNG")
    img_binary.seek(0)
    return img_binary

@tasks.loop(seconds=20)
async def update_leaderboard():
    try:
        # Fetch the channel to send the leaderboard to
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)

        if not channel:
            logger.error(f"Leaderboard channel not found: {LEADERBOARD_CHANNEL_ID}")
            return

        # Generate the leaderboard image
        image = await create_leaderboard_image()

        # Ensure image is passed as a file, not trying to log or serialize the object
        global leaderboard_message

        if leaderboard_message:
            # Delete the previous message if it exists
            await leaderboard_message.delete()

        # Send the new leaderboard message from scratch
        leaderboard_message = await channel.send(file=discord.File(image, filename="leaderboard.png"))

    except discord.HTTPException as e:
        if e.status == 429:
            # Handle rate-limiting errors
            retry_after = int(e.retry_after)
            logger.warning(f"Rate-limited. Retrying after {retry_after} seconds.")
            await asyncio.sleep(retry_after)
        else:
            logger.error(f"HTTPException while updating leaderboard: {e}")

    except Exception as e:
        logger.error(f"Unexpected error in update_leaderboard: {e}")

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
bot.run('MTMwMzQyNjkzMzU4MDc2MzIzNg.GpSZcY.4mvu2PTpCOm7EuCaUecADGgssPLpxMBrlHjzbI')  # Replace with your bot token
