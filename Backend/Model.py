import cohere
from rich import print
from dotenv import dotenv_values
import os
import sys

# PyInstaller-compatible path
BASE_DIR = getattr(sys, '_MEIPASS', os.path.abspath("."))
ENV_PATH = os.path.join(BASE_DIR, ".env")

# Load environment variables
env_vars = dotenv_values(ENV_PATH)
cohere_api_key = env_vars.get("COHERE_API_KEY")

# Initialize Cohere client
co = cohere.Client(api_key=cohere_api_key)

# List of supported functions
funcs = ["exit", "general", "realtime", "open", "close", "play", "generate-image", "system", "content", "google search", "youtube search", "reminder", "follow", "unfollow"]

# Message history
messages = []

# Preamble
preamble = '''
You are a very Accurate Decision Making Model which decides what kind of query is given to you...
[...truncated, same as your full preamble...]
'''

# Chat history
chat_history = [
    {"role": "user", "message": "How are you?"},
    {"role": "chatbot", "message": "general How are you?"},
    {"role": "user", "message": "Do you like Pizza?"},
    {"role": "chatbot", "message": "general Do you like Pizza?"},
    {"role": "user", "message": "Open Chrome and tell me about Mahatma Gandhi"},
    {"role": "chatbot", "message": "open Chrome, general Tell me about Mahatma Gandhi."},
    {"role": "user", "message": "Open Chrome and Firefox"},
    {"role": "chatbot", "message": "open Chrome, open Firefox"},
    {"role": "user", "message": "What's today's date and by the way remind me Happy Birthday on 24 March at 12am"},
    {"role": "chatbot", "message": "general What's today's date, reminder 12am 24 March Happy Birthday"},
    {"role": "user", "message": "Chat with me."},
    {"role": "chatbot", "message": "general Chat with me."}
]

def firstlayer(prompt: str = "test"):
    messages.append({"role": "user", "content": f"{prompt}"})
    stream = co.chat(
        model='command-r-plus',
        message=prompt,
        temperature=0.7,
        chat_history=chat_history,
        preamble=preamble,
        connectors=[],
        prompt_truncation='off'
    ).text
    messages.append({"role": "chatbot", "content": stream})
    return stream

def interactive_loop():
    while True:
        user_input = input("You: ")
        response = firstlayer(user_input)
        print(f"{response}")

if __name__ == "__main__":
    interactive_loop()
