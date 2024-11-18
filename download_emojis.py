# -*- coding: utf-8 -*-
import os
import requests

# Directory to save the emoji images
emoji_save_dir = "emoji_images"
os.makedirs(emoji_save_dir, exist_ok=True)

# Function to fetch emoji image from GitHub repository
def fetch_emoji_image(emoji_char):
    # Convert emoji to Unicode code point
    emoji_unicode = ''.join(format(ord(c), 'x') for c in emoji_char)  # Get Unicode code point as a hex string

    # Construct the GitHub URL for the emoji image in 72x72 folder
    emoji_url = f"https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/{emoji_unicode}.png"

    # Attempt to download the emoji image
    try:
        response = requests.get(emoji_url)
        if response.status_code == 200:
            emoji_filename = os.path.join(emoji_save_dir, f"{emoji_unicode}.png")
            with open(emoji_filename, 'wb') as f:
                f.write(response.content)
            print(f"Successfully downloaded {emoji_char} as {emoji_filename}")
        else:
            print(f"Failed to download {emoji_char}. HTTP status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {emoji_char}: {e}")

# List of emojis to download
emoji_list = ["😂", "😊", "👍", "❤️", "🔥"]

# Download each emoji
for emoji in emoji_list:
    fetch_emoji_image(emoji)
