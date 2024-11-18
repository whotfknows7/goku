import os
import requests

# Directory to save the emoji images
emoji_save_dir = "emoji_images"
os.makedirs(emoji_save_dir, exist_ok=True)

# Function to fetch emoji image from GitHub repository
def fetch_emoji_image(emoji_char):
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
emoji_unicodes = [
    "1f600", "1f603", "1f604", "1f601", "1f606", "1f605", "1f602", "1f923", "1f61c", "1f61d",
    "1f61b", "1f60e", "1f913", "1f60f", "1f612", "1f61e", "1f614", "1f61f", "1f615", "1f614",
    "2639", "1f623", "1f616", "1f62b", "1f629", "1f97a", "1f622", "1f62d", "1f624", "1f621",
    "1f620", "1f92c", "1f637", "1f912", "1f915", "1f927", "1f974", "1f635", "1f632", "1f633",
    "1f973", "1f929", "1f60e", "1f914", "1f92d", "1f92b", "1f917", "1f920", "1f63a", "1f638"
]


# Download each emoji
for emoji in emoji_list:
    fetch_emoji_image(emoji)
