import asyncio
import requests
import os
import sys
from random import randint
from PIL import Image
from time import sleep

# PyInstaller-compatible base directory
BASE_DIR = getattr(sys, '_MEIPASS', os.path.abspath("."))
IMAGES_DIR = os.path.join(BASE_DIR, "Data", "Images")

def open_images(prompt):
    """Open generated images from the Data/Images folder."""
    prompt_formatted = prompt.replace(" ", "_")
    files = [f"{prompt_formatted}_{i}.jpg" for i in range(1, 5)]

    for jpg_file in files:
        image_path = os.path.join(IMAGES_DIR, jpg_file)
        try:
            with Image.open(image_path) as img:
                print(f"Opening Image: {image_path}")
                img.show()
            sleep(1)
        except IOError:
            print(f"Unable to open {image_path}")

async def query(prompt, width=1024, height=1024, model="flux"):
    """Send a request to Pollinations AI and get the image content."""
    seed = randint(0, 1000000)
    formatted_prompt = prompt.replace(" ", "%20")
    url = f"https://pollinations.ai/p/{formatted_prompt}?width={width}&height={height}&seed={seed}&model={model}"
    print(f"Requesting image from: {url}")
    response = await asyncio.to_thread(requests.get, url)
    response.raise_for_status()
    return response.content

async def generate_image(prompt: str, width=1024, height=1024, model="flux"):
    """Generate and save 4 images asynchronously."""
    tasks = [asyncio.create_task(query(prompt, width, height, model)) for _ in range(4)]
    image_bytes_list = await asyncio.gather(*tasks)

    os.makedirs(IMAGES_DIR, exist_ok=True)
    prompt_formatted = prompt.replace(' ', '_')

    for i, image_bytes in enumerate(image_bytes_list, start=1):
        image_path = os.path.join(IMAGES_DIR, f"{prompt_formatted}_{i}.jpg")
        with open(image_path, "wb") as f:
            f.write(image_bytes)
        print(f"Saved image: {image_path}")

def generate_images(prompt: str, width=1024, height=1024, model="flux"):
    """Main function to generate and open images."""
    asyncio.run(generate_image(prompt, width, height, model))
    open_images(prompt)
