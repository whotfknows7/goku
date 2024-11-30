import discord
from discord.ext import commands, tasks
import logging
import asyncio
from datetime import datetime, timedelta
import time
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
from io import BytesIO
import os
import re
import emoji
from typing import List, Dict
import sqlite3
import signal
import sys
import traceback

# Constants
RESET_INTERVAL = timedelta(weeks=1)  # 1 week interval
D_RESET_INTERVAL = timedelta(days=1)
LAST_RESET_TIME_FILE = "last_reset_time.txt"  # File to track last reset time
D_LAST_RESET_TIME_FILE = "daily_last_reset_time.txt"
conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()
reset_task_running = False  # Global variable to track task status

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Channel IDs
ROLE_LOG_CHANNEL_ID = 1251143629943345204
LEADERBOARD_CHANNEL_ID = 1303672077068537916
GUILD_ID = 1227505156220784692  # Replace with your actual guild ID
CLAN_ROLE_1_ID = 1245407423917854754  # Replace with your actual Clan Role 1 ID
CLAN_ROLE_2_ID = 1247225208700665856

# Define intents
intents = discord.Intents.default()
intents.members = True

# Bot setup
bot = commands.Bot(command_prefix="!", intents=intents)

# Regular expressions
URL_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"

previous_top_10 = []  # Cache for storing the previous top 10 users
leaderboard_message = None
cached_top_users = []  # Cache for the last updated top 10 users
cached_image_path = "leaderboard.png"  

# Define FONT_PATH globally
FONT_PATH = "TT Fors Trial Bold.ttf"  # Adjust the path as needed

async def graceful_shutdown():
    logger.info("Shutting down bot gracefully...")
    try:
        # Stop tasks
        reset_weekly.stop()
        reset_task_running = False

        # Close database connection
        conn.close()
        logger.info("Database connection closed.")

        # Cancel all running tasks
        tasks = asyncio.all_tasks()
        for task in tasks:
            if task is not asyncio.current_task():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"Cancelled task: {task}")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

@tasks.loop(minutes=15)
async def reconnect_bot():
    global leaderboard_message  # Ensure this is declared as global if you're modifying it inside the function.

    try:
        
        # Wait for 15 minutes before disconnecting
        logger.info("Bot will stay active for 15 minutes before disconnecting.")
        await asyncio.sleep(15 * 60)  # 15 minutes in seconds
        
        # Fetch the channel and embed data (assuming this is where the image and embed come from)
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)  # Replace with your actual channel ID
        if not channel:
            logger.error(f"Leaderboard channel not found: {LEADERBOARD_CHANNEL_ID}")
            return

        if leaderboard_message:
            try:
                # Delete the previous message if it exists
                await leaderboard_message.delete()
                logger.info("Deleted previous leaderboard message before reconnecting.")
            except discord.NotFound:
                logger.info("Leaderboard message not found to delete.")
            except discord.HTTPException as e:
                logger.error(f"Failed to delete leaderboard message: {e}")

        # Disconnect the bot
        logger.info("Disconnecting bot for scheduled reconnect...")
        await bot.close()  # Disconnect the bot

        await graceful_shutdown()  # Clean up tasks and resources

        # Restart the process
        logger.info(f"Restarting bot with: {sys.executable} {sys.argv}")
        os.execv(sys.executable, ['python3'] + sys.argv)  # Restart the script

    except Exception as e:
        logger.error("Failed to restart bot process:", exc_info=True)
        with open("restart_error.log", "a") as log_file:
            log_file.write(f"{datetime.now()}: {traceback.format_exc()}\n")


@bot.event
async def on_ready():
    global reset_task_running

    try:
        logger.info(f"Bot logged in as {bot.user.name}")

        # Ensure the reset task is scheduled properly
        if not reset_task_running:
            reset_task_running = True
            bot.loop.create_task(reset_task())  # Start reset_task in the background

        # Start the weekly reset task (ensure it's running)
        if not reset_weekly.is_running():
            reset_weekly.start()  # Start the looped weekly task

        # Ensure the reconnect bot task is running
        if not reconnect_bot.is_running():
            logger.info("Starting reconnect_bot task.")
            reconnect_bot.start()
              
        # Call the leaderboard update function
        update_leaderboard.start()
        
    except Exception as e:
        logger.error(f"Error in on_ready: {e}")

@bot.event
async def on_disconnect():
    logger.warning("bot is diconnecting, cleaning up tasks")

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"An error occurred: {event}, {args}, {kwargs}")

def d_check_file_contents():
    if os.path.exists(D_LAST_RESET_TIME_FILE):
        with open(D_LAST_RESET_TIME_FILE, "r") as file:
            content = file.read()
            logger.info(f"Contents of the reset time file: {content}")
    else:
        logger.info(f"{D_LAST_RESET_TIME_FILE} does not exist.")

# Function to check contents of the file
def check_file_contents():
    if os.path.exists(LAST_RESET_TIME_FILE):
        with open(LAST_RESET_TIME_FILE, "r") as file:
            content = file.read()
            logger.info(f"Contents of the reset time file: {content}")
    else:
        logger.info(f"{LAST_RESET_TIME_FILE} does not exist.")

# Function to read the last reset time from the file
def read_last_reset_time():
    try:
        if not os.path.exists(LAST_RESET_TIME_FILE):
            # If the file doesn't exist, initialize it with the current time
            write_last_reset_time()
            return datetime.now()  # Return the current time as the last reset time

        with open(LAST_RESET_TIME_FILE, "r") as file:
            # Read and strip the content to handle any unwanted extra spaces or empty lines
            content = file.read().strip()

            if not content:  # If the file is empty
                logger.info("The reset file is empty, writing current time.")
                write_last_reset_time()  # Write current time as last reset time
                return datetime.now()  # Return the current time

            try:
                # Try to parse the content as a datetime
                return datetime.fromisoformat(content)  # Read last reset time
            except ValueError as e:
                logger.error(f"Invalid datetime format in file: {e}")
                write_last_reset_time()  # Write current time as last reset time
                return datetime.now()  # Return current time

    except Exception as e:
        # Log the error and return current time as fallback
        logger.error(f"Error reading last reset time: {e}")
        write_last_reset_time()  # Write current time as last reset time in case of error
        return datetime.now()  # Return current time

# Function to read the last reset time from the file
def d_read_last_reset_time():
    try:
        if not os.path.exists(D_LAST_RESET_TIME_FILE):
            # If the file doesn't exist, initialize it with the current time
            d_write_last_reset_time()
            return datetime.now()  # Return the current time as the last reset time

        with open(D_LAST_RESET_TIME_FILE, "r") as file:
            # Read and strip the content to handle any unwanted extra spaces or empty lines
            content = file.read().strip()

            if not content:  # If the file is empty
                logger.info("The reset file is empty, writing current time.")
                d_write_last_reset_time()  # Write current time as last reset time
                return datetime.now()  # Return the current time

            try:
                # Try to parse the content as a datetime
                return datetime.fromisoformat(content)  # Read last reset time
            except ValueError as e:
                logger.error(f"Invalid datetime format in file: {e}")
                d_write_last_reset_time()  # Write current time as last reset time
                return datetime.now()  # Return current time

    except Exception as e:
        # Log the error and return current time as fallback
        logger.error(f"Error reading last reset time: {e}")
        d_write_last_reset_time()  # Write current time as last reset time in case of error
        return datetime.now()  # Return current time
      
# Function to write the last reset time to the file
def write_last_reset_time():
    try:
        with open(LAST_RESET_TIME_FILE, "w") as file:
            current_time = datetime.now().isoformat()  # Get current time as ISO 8601 format
            file.write(current_time)  # Store current time as last reset time
            logger.info(f"Last reset time written to file: {current_time}")
    except Exception as e:
        logger.error(f"Error writing last reset time: {e}")

def d_write_last_reset_time():
    try:
        with open(D_LAST_RESET_TIME_FILE, "w") as file:
            current_time = datetime.now().isoformat()
            file.write(current_time)
            logger.info(f"Successfully wrote to {D_LAST_RESET_TIME_FILE}: {current_time}")
    except Exception as e:
        logger.error(f"Failed to write to {D_LAST_RESET_TIME_FILE}: {e}")
        raise  # Re-raise to highlight the error


# Function to calculate the remaining time before the next reset
def d_time_remaining_until_reset():
    d_last_reset_time = d_read_last_reset_time()
    if d_last_reset_time is None:
        return D_RESET_INTERVAL  # No last reset time, return 1 week interval
    d_next_reset_time = d_last_reset_time + D_RESET_INTERVAL
    d_remaining_time = d_next_reset_time - datetime.now()
    return d_remaining_time if d_remaining_time > timedelta(0) else timedelta(0)  # Return remaining time or 0 if reset is overdue

# Function to calculate the remaining time before the next reset
def time_remaining_until_reset():
    last_reset_time = read_last_reset_time()
    if last_reset_time is None:
        return RESET_INTERVAL  # No last reset time, return 1 week interval
    next_reset_time = last_reset_time + RESET_INTERVAL
    remaining_time = next_reset_time - datetime.now()
    return remaining_time if remaining_time > timedelta(0) else timedelta(0)  # Return remaining time or 0 if reset is overdue

# Function to reset the database (clear all XP data)
async def reset_database():
    try:
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute("DELETE FROM user_xp;")  # Clears all XP data
        conn.commit()
        print("Database has been reset.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error resetting the database: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"Error resetting the database: {e}\n")
            
async def reset_task():
    global reset_task_running
    try:
        while True:
            d_remaining_time = d_time_remaining_until_reset()
            logger.info(f"Daily time remaining: {d_remaining_time}")

            if d_remaining_time.total_seconds() > 0:
                await asyncio.sleep(d_remaining_time.total_seconds())

            # Perform daily reset and log success
            await reset_and_save_top_users()
            d_write_last_reset_time()
            logger.info("Daily reset completed.")
    except asyncio.CancelledError:
        logger.info("reset_task was cancelled.")
        raise  # Allow the cancellation to propagate
    except Exception as e:
        logger.error(f"Error in reset_task: {e}")
    finally:
        reset_task_running = False
    
# Function to reset the database and perform the save operation
async def reset_and_save_top_users():
    # Fetch top 10 users with their XP
    top_users = await fetch_top_10_users_and_check_roles(bot, CLAN_ROLE_1_ID, CLAN_ROLE_2_ID)

    # Save each user's XP before resetting the database
    for user in top_users:
        user_id = user['user_id']
        xp = user['xp']
        await save_user_to_clan_role_table(bot, user_id, xp)  # Save the top 10 users' XP before reset

    # Now reset the database
    await reset_database()
    print("XP data reset and top users saved.")

# Function to reset clan XP tables for both clans
async def reset_clan_xp():
    try:
        # Reset XP for both clans
        cursor.execute("DELETE FROM clan_role_1")  # Reset table for Clan 1
        cursor.execute("DELETE FROM clan_role_2")  # Reset table for Clan 2
        conn.commit()
        print("Clan XP tables have been reset.")
    except sqlite3.Error as e:
        print(f"Error resetting clan XP tables: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"Error resetting clan XP tables: {e}\n")
            
# Function to count custom emojis in a message
def count_custom_emojis(content):
    custom_emoji_pattern = r'<a?:\w+:\d+>'
    return len(re.findall(custom_emoji_pattern, content))

# Function to determine if a character is an emoji
def is_emoji(char):
    return emoji.is_emoji(char)

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
    character_xp = len(filtered_content.replace(" ", "")) * 1  # 1 XP per alphanumeric character
    custom_emoji_count = count_custom_emojis(message.content)
    unicode_emoji_count = sum(1 for c in message.content if is_emoji(c))
    emoji_xp = (custom_emoji_count + unicode_emoji_count) * 5  # 5 XP per emoji
    total_xp = character_xp + emoji_xp

    # Update user data
    from db_server import update_user_xp
    update_user_xp(user_id, total_xp)

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
  
# Cache for storing the previous top 10 users with more details (ID, XP, avatar URL, nickname)
previous_top_10 = []  # A list of dictionaries to store user data

# Modify the update function to save more information
async def fetch_top_users_with_xp() -> List[Dict]:
    """
    Fetches the top 10 users based on XP from the database.
    Returns a list of dictionaries containing user data (ID, XP, nickname, avatar URL).
    """
    
    cursor.execute("SELECT user_id, xp FROM user_xp ORDER BY xp DESC LIMIT 10")
    top_users_data = cursor.fetchall()

    # Create a list of dictionaries with user details (ID, XP, nickname, avatar URL)
    users_with_details = []
    for user_id, xp in top_users_data:
        member = await get_member(user_id)
        if member:
            nickname, avatar_url = member
            users_with_details.append({
                'user_id': user_id,
                'xp': xp,
                'nickname': nickname,
                'avatar_url': avatar_url
            })
    return users_with_details
  
# Function to download the font if not already cached
def download_font():
    if not os.path.exists(FONT_PATH):
        # If the font doesn't exist locally, download it
        font_url = "https://cdn.glitch.global/04f6dfef-4255-4a66-b865-c95597b8df08/TT%20Fors%20Trial%20Bold.ttf?v=1731866074399"
        
        response = requests.get(font_url)
        
        if response.status_code == 200:
            with open(FONT_PATH, "wb") as f:
                f.write(response.content)
            logging.info(f"Font downloaded and cached at {FONT_PATH}")
        else:
            logging.error("Failed to download font. Using default font instead.")
            
# Function to fetch member details
async def get_member(user_id):
    try:
        from db_server import delete_user_data
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            logger.error(f"Guild with ID {GUILD_ID} not found")
            return None

        member = await guild.fetch_member(user_id)
        if member:
            nickname = member.nick if member.nick else member.name
            avatar_url = member.avatar_url if member.avatar_url else None
            return nickname, avatar_url
        else:
            # If member is not found (i.e., they left the server), clean up the data
            delete_user_data(user_id)  # Clean up the data from the database
            return None
    except discord.HTTPException as e:
        # Handle HTTP exceptions (e.g., member not found)
        if e.code == 10007:  # Member not found
            delete_user_data(user_id)
            return None
        else:
            logger.error(f"Failed to fetch member {user_id} in guild {GUILD_ID}: {e}")
            return None
          
# Directory where emoji images are stored
EMOJI_DIR = "./emoji_images/"  # Update this to the correct path where emojis are saved

# Ensure the emoji directory exists
if not os.path.exists(EMOJI_DIR):
    os.makedirs(EMOJI_DIR)

def fetch_emoji_image(emoji_char):
    emoji_unicode = format(ord(emoji_char), 'x')
    emoji_filename = f"{emoji_unicode}.png"
    emoji_image_path = os.path.join(EMOJI_DIR, emoji_filename)

    if os.path.exists(emoji_image_path):
        try:
            img = Image.open(emoji_image_path).convert("RGBA")
            # Remove or comment the print statement below
            # print(f"Loaded emoji image: {emoji_image_path}")
            return img
        except Exception as e:
            logging.error(f"Failed to open image for emoji {emoji_char}: {e}")
            return None
    else:
        logging.warning(f"Emoji image not found for {emoji_char} at {emoji_image_path}")
        return None

def render_nickname_with_emoji_images(draw, img, nickname, position, font, emoji_size=28):

    text_part = ''.join([char for char in nickname if not emoji.is_emoji(char)])
    emoji_part = ''.join([char for char in nickname if emoji.is_emoji(char)])

    # Increase outline thickness
    stroke_width = 2  # Increased stroke width for thicker outline

    # Draw regular text first with outline
    draw.text(position, text_part, font=font, fill="white", stroke_width=stroke_width, stroke_fill="black")

    # Get the bounding box of the regular text to place emojis next to it
    text_bbox = draw.textbbox((0, 0), text_part, font=font)
    text_width = text_bbox[2] - text_bbox[0]  # Width of the regular text part

    # Adjust the position to draw emojis after regular text
    emoji_position = (position[0] + text_width + 5, position[1])  # No vertical offset, emojis are aligned with the text

    # Loop through each character in the emoji part and render it as an image
    for char in emoji_part:
        if emoji.is_emoji(char):  # Ensure it's an emoji
            emoji_img = fetch_emoji_image(char)  # Fetch the emoji image from local folder

            if emoji_img:
                emoji_img = emoji_img.resize((emoji_size, emoji_size))  # Resize to fit the text

                # Paste the emoji image (uses transparency properly)
                img.paste(emoji_img, emoji_position, emoji_img.convert('RGBA'))  # Use alpha channel for transparency

                # Update position for the next emoji
                emoji_position = (emoji_position[0] + emoji_size + 5, emoji_position[1])
                
def format_points(points):
    if points >= 1000:
        return f"{points / 1000:.1f}k"  # Formats as 'X.Xk'
    return str(points)
  
@bot.event
async def on_member_update(before, after):
    # If nickname or avatar changed, update the cache
    if before.nick != after.nick or before.avatar_url != after.avatar_url:
        user_id = after.id
        nickname = after.nick if after.nick else after.name
        avatar_url = after.avatar_url if after.avatar_url else None
        
        # Update profile in the cache
        updated = False
        for i, (uid, xp, av_url, _) in enumerate(previous_top_10):
            if uid == user_id:
                previous_top_10[i] = (uid, xp, avatar_url, nickname)  # Update profile info
                updated = True
                break
        
        # If the user isn't in the cached list, add them
        if not updated:
            previous_top_10.append((user_id, 0, avatar_url, nickname))  # Initialize with 0 XP

async def create_leaderboard_image():
    # Download the font if it's not already cached
    download_font()

    WIDTH = 800  # Image width
    HEIGHT = 600  # Image height
    PADDING = 10  # Padding for layout

    img = Image.new("RGBA", (WIDTH, HEIGHT), color=(0, 0, 0, 0))  # Transparent background (alpha=0)
    draw = ImageDraw.Draw(img)

    try:
        # Load the font from the local cache
        font = ImageFont.truetype(FONT_PATH, size=28)
    except IOError:
        logging.error("Failed to load custom font. Using default font instead.")
        font = ImageFont.load_default()  # Fallback to default font

    # Rank-specific background colors
    rank_colors = {
        1: "#FFD700",  # Gold for Rank 1
        2: "#E6E8FA",  # Silver for Rank 2
        3: "#CD7F32",  # Bronze for Rank 3
    }

    y_position = PADDING
    top_users = await fetch_top_users_with_xp()  # Example function to fetch users

    if not top_users:
        # If no users fetched, display a message
        draw.text((PADDING, PADDING), "Bruh sadly No-one is yapping right now...", font=font, fill="white")
    else:
        for rank, user in enumerate(top_users, 1):
            user_id = user['user_id']
            xp = user['xp']
            avatar_url = user['avatar_url']
            nickname = user['nickname']

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
                img_pfp = img_pfp.resize((57, 58))  # Resize PFP to 57x58
                img_pfp = round_pfp(img_pfp)  # Apply rounded corners to the PFP
            except Exception as e:
                logging.error(f"Failed to fetch avatar for user {user_id}: {e}")
                img_pfp = Image.new('RGBA', (57, 57), color=(128, 128, 128, 255))  # Default grey circle

            img.paste(img_pfp, (PADDING, y_position), img_pfp)  # Use the alpha mask when pasting

            # Render rank text
            rank_text = f"#{rank}"
            rank_bbox = draw.textbbox((0, 0), rank_text, font=font)
            rank_height = rank_bbox[3] - rank_bbox[1]  # Height of rank text
            rank_y_position = y_position + (57 - rank_height) // 2 - 8  # Slightly move text upwards (adjust -8 value)
            stroke_width = 2  # Increase the outline width here
            draw.text((PADDING + 65, rank_y_position), rank_text, font=font, fill="white", stroke_width=stroke_width, stroke_fill="black")

            # Calculate width for separators and nickname
            rank_width = rank_bbox[2] - rank_bbox[0]

            # Slightly decrease the gap between rank number and the first separator
            first_separator_position = PADDING + 65 + rank_width + 10  # Decreased gap by changing +15 to +10

            # Render the first "|" separator with outline
            first_separator_text = "|"
            first_separator_y_position = rank_y_position
            outline_width = 2
            outline_color = "black"
            for x_offset in range(-outline_width, outline_width + 1):
                for y_offset in range(-outline_width, outline_width + 1):
                    draw.text((first_separator_position + x_offset, first_separator_y_position + y_offset),
                              first_separator_text, font=font, fill=outline_color)
            draw.text((first_separator_position, first_separator_y_position), first_separator_text, font=font, fill="white")

            # Render the nickname with emojis
            nickname_bbox = draw.textbbox((0, 0), nickname, font=font)
            nickname_y_position = y_position + (57 - (nickname_bbox[3] - nickname_bbox[1])) // 2 - 8  # Slightly move nickname text upwards
            render_nickname_with_emoji_images(draw, img, nickname, (first_separator_position + 20, nickname_y_position), font)

            # Calculate space between nickname and second separator, taking emojis into account
            nickname_width = nickname_bbox[2] - nickname_bbox[0]  # Get width of nickname text
            emoji_gap = 12  # Extra space if there are emojis
            second_separator_position = first_separator_position + 20 + nickname_width + emoji_gap  # Add space between nickname and second separator

            # Render the second "|" separator with outline
            second_separator_y_position = nickname_y_position
            second_separator_text = "|"
            for x_offset in range(-outline_width, outline_width + 1):
                for y_offset in range(-outline_width, outline_width + 1):
                    draw.text((second_separator_position + x_offset, second_separator_y_position + y_offset),
                              second_separator_text, font=font, fill=outline_color)
            draw.text((second_separator_position, second_separator_y_position), second_separator_text, font=font, fill="white")

            # Render the XP points with space
            points_text = f"XP: {int(xp)} Pts"
            points_bbox = draw.textbbox((0, 0), points_text, font=font)
            points_height = points_bbox[3] - points_bbox[1]
            points_y_position = y_position + (57 - points_height) // 2 - 8  # Slightly move XP text upwards
            points_position = second_separator_position + 20
            draw.text((points_position, points_y_position), points_text, font=font, fill="white", stroke_width=2, stroke_fill="black")  # Increased stroke width
            
            y_position += 60  # Space for next row of text

    img_binary = BytesIO()
    img.save(img_binary, format="PNG")
    img_binary.seek(0)

    return img_binary

@bot.command(name='live')
async def live(ctx):
    """Command to immediately send the live leaderboard to the user's channel."""
    await update_leaderboard(ctx)

@tasks.loop(seconds=20)
async def update_leaderboard(ctx=None):
    """Update the leaderboard and optionally send it to the channel."""
    global previous_top_10
    global cached_top_users
    global leaderboard_message

    try:
        # Fetch the current top 10 leaderboard data with extra details
        current_top_10 = await fetch_top_users_with_xp()

        # Compare with the previous top 10 to detect changes
        if current_top_10 == previous_top_10:
            return

        # Update the cached top 10
        if previous_top_10:
            cached_top_users.append(previous_top_10)

        if len(cached_top_users) > 1:
            cached_top_users.pop(0)  # Remove the oldest cached list

        previous_top_10 = current_top_10  # Update the current top 10

        # Generate the leaderboard image
        image = await create_leaderboard_image()

        # URL of the rotating trophy GIF
        trophy_gif_url = (
            "https://cdn.discordapp.com/attachments/1303672077068537916/1308447424393511063/2ff0b4fa-5363-4bf1-81bd-835b926ec485-ezgif.com-resize.gif"
        )  # Replace with the actual URL of your GIF

        # Create the embed message
        embed = discord.Embed(
            title="🏆  Yappers of the day!",
            description="The leaderboard is live! Check the leaderboard to see if your messages have earned you a spot in the top 10 today!",
            color=discord.Color.gold()
        )
        embed.set_footer(text="To change your name on the leaderboard, go to User Settings > Account > Server Profile > Server Nickname.")
        embed.set_thumbnail(url=trophy_gif_url)

        # Set the rotating trophy GIF as the thumbnail
        embed.set_image(url="attachment://leaderboard.png")

        # If the context (ctx) is passed, send the leaderboard to the user's channel
        if ctx:
            # Send the embed and image to the user's channel
            await ctx.send("Here is the live leaderboard!", embed=embed, file=discord.File(image, filename="leaderboard.png"))
        else:
            # Send the leaderboard to the defined leaderboard channel (if periodic update)
            channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
            if not channel:
                logger.error(f"Leaderboard channel not found: {LEADERBOARD_CHANNEL_ID}")
                return
            if leaderboard_message:
                # Delete the previous message if it exists
                await leaderboard_message.delete()
            leaderboard_message = await channel.send(embed=embed, file=discord.File(image, filename="leaderboard.png"))

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

        
@bot.command(name='hi')
async def hi(ctx):
    latency = bot.latency * 1000  # Convert latency to milliseconds
    await ctx.send(f'Yes Masta! {latency:.2f}ms')
    
async def has_either_role_by_ids(bot, user_id, role_id_1, role_id_2):
    try:
        # Get the guild (replace with your actual GUILD_ID)
        guild = bot.get_guild(GUILD_ID)

        if guild is None:
            print("Guild not found.")
            return False

        # Fetch the member using user_id (use fetch_member to get from API)
        try:
            member = await guild.fetch_member(user_id)
        except discord.NotFound:
            print(f"Member with ID {user_id} not found.")
            return False
        except discord.DiscordException as e:
            print(f"Error fetching member with ID {user_id}: {e}")
            return False

        # Log member roles for debugging
        print(f"Checking roles for member {user_id} ({member.name})")
        
        # Check if the member has either of the two roles
        for role in member.roles:
            if role.id == role_id_1 or role.id == role_id_2:
                print(f"User {user_id} has one of the required roles.")
                return True
        
        print(f"User {user_id} does not have the required roles.")
        return False
    except discord.DiscordException as e:
        print(f"Error checking roles for user {user_id}: {e}")
        return False

# Fetch top 10 users with XP and check their roles
async def fetch_top_10_users_and_check_roles(bot, role_id_1, role_id_2):
    cursor.execute('''
        SELECT user_id, xp FROM user_xp
        ORDER BY xp DESC
        LIMIT 10
    ''')
    top_users = cursor.fetchall()

    # List to store users who have the required role
    users_with_role = []

    # Iterate over the top 10 users and check if they have either role
    for user_id, xp in top_users:
        has_role = await has_either_role_by_ids(bot, user_id, role_id_1, role_id_2)
        if has_role:
            users_with_role.append({'user_id': user_id, 'xp': xp})

    return users_with_role
  
async def save_user_to_clan_role_table(bot, user_id, xp):
    try:
        # Check if the user has the relevant clan role using the bot
        has_role_1 = await has_either_role_by_ids(bot, user_id, CLAN_ROLE_1_ID, CLAN_ROLE_2_ID)

        if has_role_1:
            # Only check the role once, and then determine the clan table
            if await has_either_role_by_ids(bot, user_id, CLAN_ROLE_1_ID, CLAN_ROLE_2_ID):
                clan_role = 'clan_role_1'
            else:
                clan_role = 'clan_role_2'

            # Check if the user already exists in the table
            cursor.execute(f"SELECT xp FROM {clan_role} WHERE user_id = ?", (user_id,))
            existing_xp = cursor.fetchone()

            if existing_xp:
                # User exists, update their XP
                new_xp = existing_xp[0] + xp
                cursor.execute(f"UPDATE {clan_role} SET xp = ? WHERE user_id = ?", (new_xp, user_id))
            else:
                # New user, insert their XP
                cursor.execute(f"INSERT INTO {clan_role} (user_id, xp) VALUES (?, ?)", (user_id, xp))

            # Commit the changes to the database
            conn.commit()
            print(f"XP for user {user_id} updated in {clan_role} table.")
        else:
            print(f"User {user_id} does not have the correct role.")
    except sqlite3.Error as e:
        print(f"Error saving XP for user {user_id} in the clan role table: {e}")
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error saving XP for user {user_id} in the clan role table: {e}\n")

# Function to calculate total XP for a clan
async def calculate_clan_xp(clan_role):
    cursor.execute(f"SELECT SUM(xp) FROM {clan_role}")
    result = cursor.fetchone()
    return result[0] if result[0] is not None else 0

# Function to send the clan leaderboard message
async def send_clan_comparison_leaderboard():
    # Calculate total XP for both clans
    total_xp_clan_1 = await calculate_clan_xp("clan_role_1")
    total_xp_clan_2 = await calculate_clan_xp("clan_role_2")

    # Prepare the message with emojis and clan info
    one_emoji = "<a:One:1310686608109862962>"
    two_emoji = "<a:pink_two:1310686637902004224>"
    dash_blue = "<:dash_blue:1310695526244552824>"
    clan_emoji_1 = "<:grove_Street:1312395110570528828>"
    
    # Prepare the message
    comparison_message = (
        f"**🏆  Weekly Clan Leaderboard!  🏆**\n\n"  # Added newline after heading
        f"{one_emoji}{dash_blue}{clan_emoji_1}  <@&{CLAN_ROLE_1_ID}>  `{total_xp_clan_1:,}` XP Pts\n"  # Ping Clan Role 1
        f"{two_emoji}{dash_blue}<@&{CLAN_ROLE_2_ID}>  `{total_xp_clan_2:,}` XP Pts\n"  # Ping Clan Role 2
    )

    # Send the message to the desired channel
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)  # Change to the desired channel ID
    await channel.send(comparison_message)

# Command definition for !clans
@bot.command()
async def clans(ctx):
    """Command to send the clan comparison leaderboard."""
    await send_clan_comparison_leaderboard()

@tasks.loop(seconds=604800)
async def reset_weekly():
    try:
        remaining_time = time_remaining_until_reset()
        logger.info(f"Time remaining until next reset: {remaining_time}")

        if remaining_time > timedelta(0):
            await asyncio.sleep(remaining_time.total_seconds())

        await send_clan_comparison_leaderboard()
        await reset_clan_xp()
        await reset_and_save_top_users()
        write_last_reset_time()
    except asyncio.CancelledError:
        logger.info("reset_weekly task was cancelled.")
        raise
    except Exception as e:
        logger.error(f"Error in reset_weekly task: {e}")

def shutdown_handler():
    logger.info("Shutting down bot... Cancelling tasks.")
    for task in asyncio.all_tasks():
        logger.info(f"Cancelling task: {task}")
        task.cancel()

loop = asyncio.get_event_loop()
loop.add_signal_handler(signal.SIGINT, shutdown_handler)  # Handle Ctrl+C
        
async def close_bot():
    logger.info("Closing bot and cleaning up resources.")
    try:
        await bot.close()
        conn.close()
        logger.info("Database connection closed.")
    except Exception as e:
        logger.error(f"Error during bot cleanup: {e}")

if __name__ == "__main__":
    try:
        bot.run('MTMwMzQyNjkzMzU4MDc2MzIzNg.GtV2My.Z76kCOt4VKCzCc3jvmIzA_mfhiSrtCo-geUZos')
    except KeyboardInterrupt:
        asyncio.run(close_bot())
      
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
