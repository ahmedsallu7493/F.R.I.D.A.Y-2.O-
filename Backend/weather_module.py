import requests
from datetime import datetime
from groq import Groq
from dotenv import dotenv_values

# Load Groq API key from .env
env = dotenv_values(".env")
GroqAPIKey = env.get("GroqAPIKey")

if not GroqAPIKey:
    raise ValueError("❌ GroqAPIKey is missing in .env file.")

client = Groq(api_key=GroqAPIKey)

def format_to_ampm(dt_string):
    try:
        dt = datetime.strptime(dt_string, "%Y-%m-%dT%H:%M:%S%z")
        return dt.strftime("%I:%M %p")
    except Exception:
        return "N/A"

def get_weather_report(city="Surat", state="Gujarat", lat="21.1702", lon="72.8311"):
    url = f"https://weather-api180.p.rapidapi.com/weather/weather/{lat}/{lon}/current"
    headers = {
        "x-rapidapi-key": "ae5a5fdf88msha285a7f3ee6a345p1e4365jsna90053488b92",
        "x-rapidapi-host": "weather-api180.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()

        if "data" not in result or not result["data"]:
            return "⚠️ Sorry, couldn't retrieve weather data for your location."

        data = result["data"]

        # Extract relevant fields
        weather_facts = {
            "city": city,
            "state": state,
            "updated_time": format_to_ampm(data.get("validTimeLocal", "")),
            "temperature": data.get("temperature", "N/A"),
            "feels_like": data.get("temperatureFeelsLike", "N/A"),
            "condition": data.get("wxPhraseLong", "N/A"),
            "humidity": data.get("relativeHumidity", "N/A"),
            "wind_speed": data.get("windSpeed", "N/A"),
            "wind_dir": data.get("windDirectionCardinal", "N/A"),
            "visibility": data.get("visibility", "N/A"),
            "uv_index": data.get("uvIndex", "N/A"),
            "uv_desc": data.get("uvDescription", "N/A"),
            "sunrise": format_to_ampm(data.get("sunriseTimeLocal", "")),
            "sunset": format_to_ampm(data.get("sunsetTimeLocal", ""))
        }

        # Format Groq prompt
        prompt = (
            f"Create a friendly and natural-sounding weather report for {city}, {state}:\n"
            f"- Last updated at {weather_facts['updated_time']}\n"
            f"- Temperature: {weather_facts['temperature']}°C, feels like {weather_facts['feels_like']}°C\n"
            f"- Condition: {weather_facts['condition']}\n"
            f"- Humidity: {weather_facts['humidity']}%\n"
            f"- Wind: {weather_facts['wind_speed']} km/h from {weather_facts['wind_dir']}\n"
            f"- Visibility: {weather_facts['visibility']} km\n"
            f"- UV Index: {weather_facts['uv_index']} ({weather_facts['uv_desc']})\n"
            f"- Sunrise at {weather_facts['sunrise']}, Sunset at {weather_facts['sunset']}\n\n"
            f"Please present this as a spoken message from a friendly virtual assistant."
        )

        # Query Groq (LLaMA)
        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that speaks like a human."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300,
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
        return f"⚠️ Network error while fetching weather: {e}"
    except Exception as e:
        return f"⚠️ Unexpected error: {e}"


# Test only
if __name__ == "__main__":
    print(get_weather_report())
