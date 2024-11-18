# -*- coding: utf-8 -*-

import os
import requests

# List of emoji Unicode characters (can be expanded as needed)
emojis = ["😂", "😊", "👍", "❤️", "🔥"]

# Directory to save emoji images
EMOJI_DIR = "path/to/emojis/"  # Update this path

# Ensure the directory exists
if not os.path.exists(EMOJI_DIR):
    os.makedirs(EMOJI_DIR)

# Function to download emoji images from Twemoji GitHub
def download_emoji_image(emoji_char):
    # Convert emoji to Unicode escape format (e.g., 😂 -> 1f602)
    emoji_unicode = emoji_char.encode('unicode_escape').decode('utf-8')[2:]
    emoji_filename = f"{emoji_unicode}.png"  # PNG format for the emoji image

    # GitHub URL to fetch the emoji image
    emoji_url = f"https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/{emoji_unicode}.png"

    try:
        # Request the image from the GitHub repository
        response = requests.get(emoji_url)

        if response.status_code == 200:
            # Save the emoji image to the local directory
            emoji_image_path = os.path.join(EMOJI_DIR, emoji_filename)
            with open(emoji_image_path, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded {emoji_char} to {emoji_image_path}")
        else:
            print(f"Failed to download {emoji_char}. HTTP status code: {response.status_code}")
    except Exception as e:
        print(f"Error downloading {emoji_char}: {e}")

# Download all emoji images
for emoji in emojis:
    download_emoji_image(emoji)
