import os
import requests

# Path to the folder where the images will be saved
ROLE_IMAGES_FOLDER = "./level_roles/"

# List of image URLs (paste your image URLs here)
image_urls = {
    "🧔Homo Sapien": "https://cdn.glitch.global/04f6dfef-4255-4a66-b865-c95597b8df08/Homo%20sapien%20(4).png?v=1732993113715",
    "🏆Homie": "https://cdn.glitch.global/04f6dfef-4255-4a66-b865-c95597b8df08/Homo%20sapien%20(5).png?v=1732993118399",
    "🥉VETERAN": "https://cdn.glitch.global/04f6dfef-4255-4a66-b865-c95597b8df08/Homo%20sapien%20(3).png?v=1732993017671",
    "🥈ELITE": "https://cdn.glitch.global/04f6dfef-4255-4a66-b865-c95597b8df08/Homo%20sapien%20(6).png?v=1732993125632",
    "🥇MYTHIC": "https://cdn.glitch.global/04f6dfef-4255-4a66-b865-c95597b8df08/Homo%20sapien%20(7).png?v=1732993127780",
    "⭐VIP": "https://cdn.glitch.global/04f6dfef-4255-4a66-b865-c95597b8df08/Homo%20sapien%20(9).png?v=1732993138208",
    "✨LEGENDARY": "https://cdn.glitch.global/04f6dfef-4255-4a66-b865-c95597b8df08/Homo%20sapien%20(8).png?v=1732993131218"
}

# Function to download and save the image
def download_image(role_name, url):
    # Create the role_images folder if it doesn't exist
    if not os.path.exists(ROLE_IMAGES_FOLDER):
        os.makedirs(ROLE_IMAGES_FOLDER)

    # Get the image content from the URL
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            # Format the file path to save the image
            file_path = os.path.join(ROLE_IMAGES_FOLDER, f"{role_name.replace(' ', '_')}.jpg")

            # Save the image to the file path
            with open(file_path, 'wb') as image_file:
                for chunk in response.iter_content(1024):
                    image_file.write(chunk)
            print(f"Image for '{role_name}' downloaded successfully.")
        else:
            print(f"Failed to download image for '{role_name}'. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error downloading image for '{role_name}': {e}")

# Iterate over the image URLs and download each one
for role, url in image_urls.items():
    download_image(role, url)
