# TextToSpeech.py
import requests
import random
import asyncio
import os
import playsound
from urllib.parse import quote_plus
from rich import print

# Constants
DATA_FOLDER = "Data"
TTS_FILE = os.path.join(DATA_FOLDER, "speech.mp3")
AssistantVoice = "Aditi"  # You can change this dynamically if needed

# Ensure Data folder exists
os.makedirs(DATA_FOLDER, exist_ok=True)

async def TextToAudioFile(text: str) -> None:
    """
    Asynchronously downloads TTS audio and saves it to a file.
    """
    try:
        if os.path.exists(TTS_FILE):
            os.remove(TTS_FILE)

        encoded_text = quote_plus(text)
        url = f"https://api.streamelements.com/kappa/v2/speech?voice={AssistantVoice}&text={encoded_text}"
        headers = {'User-Agent': 'Mozilla/5.0'}

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            with open(TTS_FILE, "wb") as file:
                file.write(response.content)
        else:
            print(f"[red]Error: TTS API returned status {response.status_code}[/red]")

    except Exception as e:
        print(f"[red]Voice generation error: {e}[/red]")

def TTS(text: str, callback=lambda r=None: True) -> bool:
    """
    Synchronously generates and plays back TTS audio.
    """
    try:
        asyncio.run(TextToAudioFile(text))
        if os.path.exists(TTS_FILE):
            playsound.playsound(TTS_FILE)
            return True
        else:
            print("[yellow]Audio file not found after generation.[/yellow]")

    except Exception as e:
        print(f"[red]Error in TTS playback: {e}[/red]")

    finally:
        try:
            callback(False)
            if os.path.exists(TTS_FILE):
                os.remove(TTS_FILE)
        except Exception as e:
            print(f"[yellow]Cleanup error: {e}[/yellow]")

    return False

def TextToSpeech(text: str, callback=lambda r=None: True) -> None:
    """
    Smart TTS with shortened response for long text.
    """
    segments = str(text).split("-")

    endings = [
        "Please check the chat screen for the remaining text.",
        "You can see more information on your screen now.",
        "Sir, the rest of the answer is available in the chat.",
        "Check the rest of the message on the screen, sir.",
        "You'll find more details in the chat window."
    ]

    if len(segments) > 4 and len(text) >= 250:
        intro = " ".join(text.split(".")[0:2]) + ". "
        summary = intro + random.choice(endings)
        TTS(summary, callback)
    else:
        TTS(text, callback)

if __name__ == "__main__":
    while True:
        user_input = input("Enter the Text: ")
        TextToSpeech(user_input)
