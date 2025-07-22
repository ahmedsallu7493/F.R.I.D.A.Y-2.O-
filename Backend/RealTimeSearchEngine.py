import requests
from googlesearch import search
from groq import Groq
from json import load, dump
from dotenv import dotenv_values
import datetime
import os
import sys
from rich import print

# --- PyInstaller Safe Paths ---
BASE_DIR = getattr(sys, '_MEIPASS', os.path.abspath("."))
ENV_PATH = os.path.join(BASE_DIR, ".env")
DATA_DIR = os.path.join(BASE_DIR, "Data")
CHAT_LOG_PATH = os.path.join(DATA_DIR, "ChatLog.json")

# Load environment variables
env_vars = dotenv_values(ENV_PATH)
Username = env_vars.get("Username", "User")
Assistance = env_vars.get("Assistance", "AI Assistant")
GroqAPIKey = env_vars.get("GroqAPIKey")

if not GroqAPIKey:
    raise ValueError("Error: GroqAPIKey is missing in .env file")

client = Groq(api_key=GroqAPIKey)


# ------------------------------
# Chat log functions
# ------------------------------
def load_chat_log():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CHAT_LOG_PATH):
        with open(CHAT_LOG_PATH, "w") as f:
            dump([], f)
    with open(CHAT_LOG_PATH, "r") as f:
        return load(f)

def save_chat_log(messages):
    with open(CHAT_LOG_PATH, "w") as f:
        dump(messages, f, indent=4)

# ------------------------------
# Text cleanup
# ------------------------------
def answer_modifier(answer):
    blacklist_phrases = [
        "I'm a large language model", "Please note that", "I suggest checking",
        "You can also search for", "reliable weather website", "Weather.com",
        "AccuWeather", "News channel", "mobile app", "look for local news",
        "<|header_start|>", "<|header_end|>", "Is there anything else I can help you with?",
        "Let me know if", "I can't access real-time"
    ]
    stop_keywords = ["Sunset", "Volume", "Today's top news headlines are:"]
    cleaned_lines, seen_lines = [], set()
    stop_triggered = False

    for line in answer.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(bad.lower() in stripped.lower() for bad in blacklist_phrases):
            continue
        if any(stripped.startswith(k) for k in stop_keywords):
            stop_triggered = True
            continue
        if stop_triggered:
            continue
        if stripped not in seen_lines:
            cleaned_lines.append(stripped)
            seen_lines.add(stripped)

    return "\n".join(cleaned_lines)

def real_time_info():
    now = datetime.datetime.now()
    return (
        f"Use this real-time information if needed:\n"
        f"Day: {now.strftime('%A')}\n"
        f"Date: {now.strftime('%d')}\n"
        f"Month: {now.strftime('%m')}\n"
        f"Year: {now.strftime('%Y')}\n"
        f"Hour: {now.strftime('%H')}\n"
        f"Minute: {now.strftime('%M')}\n"
        f"Second: {now.strftime('%S')}\n"
    )

def google_search(query):
    try:
        results = list(search(query, num=5))
        return f"The search results for '{query}' are:\n[start]\n" + "\n".join(
            [f"{i + 1}. {link}" for i, link in enumerate(results)]
        ) + "\n[end]"
    except Exception as e:
        return f"[red]Error occurred during Google search: {str(e)}[/red]"

def detect_intent(prompt):
    keywords = {
        "weather": ["weather", "temperature", "climate"],
        "stock": ["stock", "share", "market", "price"],
        "news": ["news", "headlines", "update"]
    }
    for intent, words in keywords.items():
        if any(word in prompt.lower() for word in words):
            return intent
    return "general"

def extract_stock_symbol(prompt):
    instruction = (
        "Extract only the stock symbol or company name from this query. "
        "For example, from 'What is the stock price of Tata?' return 'TCS' or 'TATA'. No explanation."
    )
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=20,
        stream=False
    )
    return response.choices[0].message.content.strip().upper()

def call_module(prompt):
    intent = detect_intent(prompt)

    if intent == "weather":
        from Backend.weather_module import get_weather_report
        return answer_modifier(get_weather_report(prompt))

    elif intent == "stock":
        from Backend.stock_module import get_stock_info
        company = extract_stock_symbol(prompt)
        mapping = {
            "TATA": "TCS.NS",
            "TCS": "TCS.NS",
            "RELIANCE": "RELIANCE.NS",
            "INFOSYS": "INFY.NS",
            "HDFC": "HDFCBANK.NS"
        }
        symbol = mapping.get(company, company + ".NS")
        return answer_modifier(get_stock_info(symbol))

    elif intent == "news":
        from Backend.news_module import get_important_news
        return answer_modifier(get_important_news())

    return None

system_instructions = f"""You are {Assistance}, a helpful AI assistant.
Answer queries in clear and friendly natural language.
Never show raw code, JSON, or APIs unless asked.
Avoid technical format unless absolutely required.
Just talk like a human friend would.
"""

def RealtimeSearchEngine(prompt):
    try:
        intent = detect_intent(prompt)

        if intent in ["weather", "stock", "news"]:
            return call_module(prompt)

        # General query via Groq + Google
        messages = load_chat_log()
        messages.append({"role": "user", "content": prompt})

        search_result = google_search(prompt)
        system_chat = [
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": f"Here are the search results to help you answer: {search_result}"},
            {"role": "user", "content": f"Use this real-time info: {real_time_info()}"},
            {"role": "user", "content": prompt}
        ]
        full_context = system_chat + messages

        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=full_context,
            temperature=0.7,
            max_tokens=2048,
            top_p=1,
            stream=True
        )

        answer = ""
        for chunk in completion:
            content = getattr(chunk.choices[0].delta, 'content', None)
            if content:
                answer += content

        return answer_modifier(answer.strip().replace("</s>", " "))

    except Exception as e:
        return f"[red]An error occurred: {str(e)}[/red]"

# Test
if __name__ == "__main__":
    while True:
        prompt = input("Enter your query: ").strip()
        if prompt:
            print(RealtimeSearchEngine(prompt))
