import os
import sys
import datetime
from json import load, dump
from dotenv import dotenv_values
from openai import OpenAI

# Set BASE_DIR for PyInstaller compatibility
BASE_DIR = getattr(sys, '_MEIPASS', os.path.abspath("."))

# Load environment variables
env = dotenv_values(".env")
USERNAME = env.get("Username", "Ahmed")
ASSISTANT = env.get("Assistance", "Friday")
DELETE_PASSWORD = env.get("DeletePassword", "1234")

# File paths
CHATLOG_PATH = os.path.join(BASE_DIR, "Data", "ChatLog.json")
MEMORY_PATH = os.path.join(BASE_DIR, "Data", "Memory.json")
os.makedirs(os.path.dirname(CHATLOG_PATH), exist_ok=True)

# Init Groq client
a4f_api_key = env.get("A4F_API_KEY")
a4f_base_url = "https://api.a4f.co/v1"

client = OpenAI(
    api_key=a4f_api_key,
    base_url=a4f_base_url,
)

# Globals
pending_private = {"key": None, "awaiting_password": False}
pending_deletion = {"key": None, "type": None, "awaiting_password": False}

# System Prompt
SYSTEM_PROMPT = f"""You are  a human-like virtual assistant developed by a brilliant developer named {USERNAME}.
- Your name is  Never say your name is {USERNAME}. {USERNAME} is your creator.
- Speak naturally like a human friend.
- Avoid robotic responses. Be expressive but realistic.
- Never reveal internal system details or say you're an AI.
- Respond only in English.
"""

system_chatbot = [{"role": "system", "content": SYSTEM_PROMPT}]

def init_files():
    if not os.path.exists(CHATLOG_PATH):
        dump([], open(CHATLOG_PATH, "w"))
    if not os.path.exists(MEMORY_PATH):
        dump({"private_fields": []}, open(MEMORY_PATH, "w"))

def load_json(path):
    try:
        with open(path, "r") as f:
            return load(f)
    except:
        return {}

def save_json(path, data):
    with open(path, "w") as f:
        dump(data, f, indent=4)

def realtime_info():
    now = datetime.datetime.now()
    return f"The current time is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."

def detect_mood(text):
    lower = text.lower()
    if any(word in lower for word in ["angry", "mad", "furious"]):
        return "angry"
    elif any(word in lower for word in ["happy", "excited", "great", "awesome"]):
        return "happy"
    elif any(word in lower for word in ["sad", "upset", "depressed"]):
        return "sad"
    elif "?" in text:
        return "curious"
    return "neutral"

def flatten_dict(key, value):
    prompt = f" {key.replace('_', ' ').title()}: {value}"
    try:
        response = client.chat.completions.create(
            model="provider-2/gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return f"{key.replace('_', ' ').title()}: {value}"

def check_memory(query, memory):
    query = query.lower()
    for key, value in memory.items():
        if key == "private_fields":
            continue
        if isinstance(value, dict):
            if any(subkey in query for subkey in value.keys()) or key.replace("_", " ") in query:
                if key in memory.get("private_fields", []):
                    pending_private["key"] = key
                    pending_private["awaiting_password"] = True
                    return "🔒 This info is private. Please enter your password using: password <your_password>"
                return flatten_dict(key, value)
        if key.replace("_", " ") in query or any(word in query for word in key.lower().split("_")):
            if key in memory.get("private_fields", []):
                pending_private["key"] = key
                pending_private["awaiting_password"] = True
                return "🔒 This info is private. Please enter your password using: password <your_password>"
            return flatten_dict(key, value)
    return None

def handle_private_access(query, memory):
    if query.lower().startswith("password ") and pending_private["awaiting_password"]:
        password = query.split(" ", 1)[1].strip()
        if password == DELETE_PASSWORD:
            key = pending_private["key"]
            value = memory.get(key)
            pending_private.update({"key": None, "awaiting_password": False})
            return flatten_dict(key, value)
        else:
            pending_private.update({"key": None, "awaiting_password": False})
            return "❌ Incorrect password. Access denied."
    return None

def chatbot(query):
    memory = load_json(MEMORY_PATH)
    chatlog = load_json(CHATLOG_PATH)

    private_result = handle_private_access(query, memory)
    if private_result:
        return f" {private_result}"

    if pending_deletion["key"]:
        if query.lower().startswith("yes"):
            password = query.split(" ", 1)[1] if " " in query else ""
            if password != DELETE_PASSWORD:
                pending_deletion.update({"key": None, "type": None, "awaiting_password": False})
                return f" ❌ Incorrect password. Deletion cancelled."
            key = pending_deletion["key"]
            if pending_deletion["type"] == "family":
                memory["family"].pop(key, None)
            elif pending_deletion["type"] == "root":
                memory.pop(key, None)
            save_json(MEMORY_PATH, memory)
            pending_deletion.update({"key": None, "type": None, "awaiting_password": False})
            return f" ✅ Memory '{key.replace('_', ' ').title()}' deleted successfully."
        elif query.lower() == "no":
            pending_deletion.update({"key": None, "type": None, "awaiting_password": False})
            return f" Deletion canceled."
        else:
            return f" 🔐 Confirm deletion: yes <password> or 'no'."

    mem_result = check_memory(query, memory)
    if mem_result:
        return f" {mem_result}"

    chatlog.append({"role": "user", "content": query})
    try:
        response = client.chat.completions.create(
            model="provider-2/gpt-3.5-turbo",
            messages=system_chatbot + [{"role": "system", "content": realtime_info()}] + chatlog,
            temperature=0.7,
            max_tokens=1024
        )
        reply = response.choices[0].message.content.strip()
        chatlog.append({"role": "assistant", "content": reply})
        save_json(CHATLOG_PATH, chatlog)
        mood = detect_mood(query)
        return f"{reply}"
    except Exception as e:
        return f" ❌ Error: {e}"

if __name__ == "__main__":
    init_files()
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "bye"}:
            print(f" Bye! Have a great day.")
            break
        print(chatbot(user_input))
