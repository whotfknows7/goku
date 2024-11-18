import os
import requests

# Directory where emoji images will be stored
EMOJI_DIR = "./emoji_images/"

# Ensure the emoji directory exists
if not os.path.exists(EMOJI_DIR):
    os.makedirs(EMOJI_DIR)

# List of hand and finger pointing emojis (including the peace symbol)
emoji_list = [
    "👈", "👉", "👆", "👇", "✋", "🤚", "👋", "🫵", "🤞", "✌️"
]

# Base URL for emoji images (you might need to change this if a different source is used)
BASE_URL = "https://emojipedia.org/emoji/%s/"

# Function to fetch and download emoji image
def download_emoji_image(emoji_char):
    # Convert emoji to Unicode format using ord() to match filenames
    emoji_unicode = format(ord(emoji_char), 'x')  # e.g., "1f602" for 😂
    emoji_filename = f"{emoji_unicode}.png"  # Image file format for the emoji
    emoji_image_path = os.path.join(EMOJI_DIR, emoji_filename)

    if not os.path.exists(emoji_image_path):
        print(f"Downloading image for emoji: {emoji_char}")
        try:
            # Construct the image URL and fetch the image
            emoji_url = BASE_URL % emoji_unicode
            response = requests.get(emoji_url)
            
            # Check if the response was successful
            if response.status_code == 200:
                with open(emoji_image_path, "wb") as f:
                    f.write(response.content)
                print(f"Successfully downloaded: {emoji_image_path}")
            else:
                print(f"Failed to fetch image for emoji {emoji_char}: {response.status_code}")
        except Exception as e:
            print(f"Error downloading emoji {emoji_char}: {e}")
    else:
        print(f"Emoji image already exists for {emoji_char}, skipping.")

# Download images for all emojis in the list
for emoji in emoji_list:
    download_emoji_image(emoji)

print("Finished downloading emojis.")
