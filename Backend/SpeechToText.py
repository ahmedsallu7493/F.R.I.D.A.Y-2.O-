from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from deep_translator import GoogleTranslator
import os
from rich import print

# Path to your speech recognition HTML file
HTML_FILE_PATH = os.path.abspath("Data/voice.html")  # ✅ safer relative path

# Chrome options for silent/background mode
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--log-level=3")
chrome_options.add_argument("--disable-logging")
chrome_options.add_argument("--use-fake-ui-for-media-stream")
chrome_options.add_argument("--use-fake-device-for-media-stream")

# Initialize Chrome driver silently
service = Service(ChromeDriverManager().install(), service_log_path=os.devnull)
driver = webdriver.Chrome(service=service, options=chrome_options)

# Load voice.html
driver.get(f"file:///{HTML_FILE_PATH}")

# Common question words to check for natural punctuation
question_words = {"who", "what", "when", "where", "why", "how", "which", "whom", "whose"}

def speech_recognition(timeout=15):
    """
    Activate voice recognition on the HTML page and return recognized speech.
    Returns:
        dict: {'error': False, 'translated': text} on success
              {'error': True, 'message': error_message} on failure
    """
    try:
        driver.find_element(By.ID, "start").click()
        print("[green]🎙 Listening...[/green]")

        wait = WebDriverWait(driver, timeout)
        text = ""

        try:
            text = wait.until(lambda d: d.find_element(By.ID, "output").text.strip().lower() or False)
        except TimeoutException:
            return {"error": True, "message": "🕒 No speech detected within timeout."}

        driver.find_element(By.ID, "end").click()

        # Auto add punctuation if it looks like a question
        words = text.split()
        if any(q in words for q in question_words) and not text.endswith(("?", ".", "!")):
            text += "?"

        return {"error": False, "translated": text}

    except Exception as e:
        return {"error": True, "message": f"❌ Speech recognition error: {e}"}


def translate_to_english(text):
    """
    Translate any language input into English using Deep Translator.
    """
    if not text:
        return "[red]⚠ No text recognized[/red]"
    try:
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        return translated
    except Exception as e:
        print(f"[red]Translation error: {e}[/red]")
        return "[red]I couldn’t understand what you said.[/red]"


# Test run
if __name__ == "__main__":
    result = speech_recognition()
    if result["error"]:
        print(f"[bold red]Error:[/bold red] {result['message']}")
    else:
        print(f"[cyan]🗣 You said:[/cyan] {result['translated']}")
        translated = translate_to_english(result["translated"])
        print(f"[bold green]🔤 Translated:[/bold green] {translated}")
