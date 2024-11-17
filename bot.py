
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
from PIL import Image, ImageDraw, ImageFont, ImageFilter
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

# Constants for image dimensions
WIDTH, HEIGHT = 702, 610  # Set image size
PADDING = 10  # Space from the edges of the image

font_url = "https://cdn.glitch.global/04f6dfef-4255-4a66-b865-c95597b8df08/TT%20Fors%20Trial%20Bold.ttf?v=1731866074399"

response = requests.get(font_url)
if response.status_code == 200:
    with open("TT Fors Trial Bold.ttf", "wb") as f:
        f.write(response.content)
    print("Font downloaded successfully.")
else:
    print("Failed to download font.")

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

    # Fetch fonts
    font_url = "https://cdn.glitch.global/04f6dfef-4255-4a66-b865-c95597b8df08/TT%20Fors%20Trial%20Bold.ttf?v=1731866074399"
    response = requests.get(font_url)
    if response.status_code == 200:
        with open("TT Fors Trial Bold.ttf", "wb") as f:
            f.write(response.content)
        font = ImageFont.truetype("TT Fors Trial Bold.ttf", size=24)
    else:
        logger.error("Failed to download font. Using default font instead.")
        font = ImageFont.load_default()  # Fallback to default font

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
            rank_bg_color = rank_colors.get(rank, "#F8F8F8")  # Default to light grey if rank isn't listed

            # Draw the rounded rectangle for the rank
            draw.rounded_rectangle(
                [(PADDING, y_position), (WIDTH - PADDING, y_position + 57)],
                radius=10,  # Adjust radius for corner rounding
                fill=rank_bg_color
            )

            # Fetch user profile picture
            try:
                response = requests.get(avatar_url)
                img_pfp = Image.open(BytesIO(response.content)).resize((pfp_size, pfp_size)) if response.status_code == 200 else Image.new('RGBA', (pfp_size, pfp_size), (128, 128, 128, 255))
                img_pfp = round_pfp(img_pfp)
                img.paste(img_pfp, (PADDING, y_position), img_pfp)
   
                # Set consistent text baseline
                text_y_center = y_position + (pfp_size // 2)
                text_baseline = text_y_center - (font.getbbox("A")[3] - font.getbbox("A")[1]) // 2

                # Rank
            rank_text = f"#{rank}"
            draw.text((text_padding_x, text_baseline), rank_text, font=font, fill="white", stroke_width=1, stroke_fill="black")

            # Separator 1
            sep1_x = text_padding_x + font.getbbox(rank_text)[2] + 10
            draw.text((sep1_x, text_baseline), "|", font=font, fill="white", stroke_width=1, stroke_fill="black")

            # Nickname
            nickname_x = sep1_x + font.getbbox("|")[2] + 10
            draw.text((nickname_x, text_baseline), nickname, font=font, fill="white", stroke_width=1, stroke_fill="black")

            # Separator 2
            sep2_x = nickname_x + font.getbbox(nickname)[2] + 10
            draw.text((sep2_x, text_baseline), "|", font=font, fill="white", stroke_width=1, stroke_fill="black")

            # Points
            points_text = f"XP: {int(xp)} Pts"
            points_x = sep2_x + font.getbbox("|")[2] + 10
            draw.text((points_x, text_baseline), points_text, font=font, fill="white", stroke_width=1, stroke_fill="black")

            y_position += pfp_size + 10

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
