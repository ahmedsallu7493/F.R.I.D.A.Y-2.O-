import requests
from datetime import datetime, timedelta, timezone
from dotenv import dotenv_values
from groq import Groq
import os
import sys

# PyInstaller-compatible path handling
BASE_DIR = getattr(sys, '_MEIPASS', os.path.abspath("."))
ENV_PATH = os.path.join(BASE_DIR, ".env")

# Load API keys
env = dotenv_values(ENV_PATH)
groq_api_key = env.get("GroqAPIKey")
client = Groq(api_key=groq_api_key)

def get_important_news():
    now = datetime.now(timezone.utc)
    min_date = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    url = f"https://api.worldnewsapi.com/search-news?source-country=in&language=en&min-publish-date={min_date}"
    headers = {
        "x-api-key": "0075b1b7e02a4c118a35ffe2fd17cdee"
    }

    priority_keywords = ['breaking', 'alert', 'update', 'urgent', 'crisis', 'emergency', 'warning']

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        articles = data.get("news", [])

        if not articles:
            return "There doesn't seem to be any major news updates at the moment."

        # Prioritize breaking news
        important = [a for a in articles if any(k in a.get('title', '').lower() for k in priority_keywords)]
        general = [a for a in articles if a not in important]
        top_news = (important + general)[:10]

        # Format prompt for Groq
        headlines = "\n".join([f"{i + 1}. {a['title']}" for i, a in enumerate(top_news)])
        prompt = (
            f"Summarize the following news headlines in a friendly, natural tone:\n\n"
            f"{headlines}\n\n"
            f"Do not include numbering or titles, just a clean summary as if telling a user about today’s news."
        )

        # Call Groq LLaMA
        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": "You are a smart assistant that summarizes news in human-style English."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=500,
            top_p=1,
            stream=True
        )

        result = ""
        for chunk in completion:
            content = getattr(chunk.choices[0].delta, "content", None)
            if content:
                result += content

        return result.strip()

    except requests.exceptions.RequestException as e:
        return f"Sorry, I couldn’t fetch the news due to a network issue: {e}"
    except Exception as e:
        return f"Oops, something went wrong while processing news: {e}"

# Standalone test
if __name__ == "__main__":
    print(get_important_news())
