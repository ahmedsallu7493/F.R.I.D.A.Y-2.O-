import yfinance as yf
import requests
from dotenv import dotenv_values
from groq import Groq

# Load from .env
env = dotenv_values(".env")
ALPHA_API_KEY = env.get("ALPHA_VANTAGE_KEY")
GroqAPIKey = env.get("GroqAPIKey")
client = Groq(api_key=GroqAPIKey)

def is_valid_stock_yf(symbol):
    try:
        hist = yf.Ticker(symbol).history(period="1d")
        return not hist.empty
    except Exception:
        return False

def get_stock_info_alpha(symbol):
    """Fetch from Alpha Vantage if yfinance fails."""
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={ALPHA_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()

        if "Time Series (Daily)" not in data:
            error_msg = data.get("Note") or data.get("Error Message") or "Unknown issue"
            return {"error": True, "message": error_msg}

        latest_day = next(iter(data["Time Series (Daily)"]))
        info = data["Time Series (Daily)"][latest_day]

        return {
            "source": "Alpha Vantage",
            "symbol": symbol,
            "date": latest_day,
            "open": info["1. open"],
            "high": info["2. high"],
            "low": info["3. low"],
            "close": info["4. close"],
            "volume": info["5. volume"]
        }

    except Exception as e:
        return {"error": True, "message": str(e)}

def format_stock_prompt(stock_data):
    return (
        f"Create a human-style summary for the following stock data:\n"
        f"Stock Symbol: {stock_data['symbol']}\n"
        f"Source: {stock_data['source']}\n"
        f"Date: {stock_data.get('date', 'N/A')}\n"
        f"Open: ₹{stock_data.get('open', 'N/A')}\n"
        f"High: ₹{stock_data.get('high', 'N/A')}\n"
        f"Low: ₹{stock_data.get('low', 'N/A')}\n"
        f"Close: ₹{stock_data.get('close', 'N/A')}\n"
        f"Volume: {stock_data.get('volume', 'N/A')}\n"
        f"Write the response as if you're a financial assistant, in natural, helpful English."
    )

def get_natural_stock_response(stock_data):
    """Send stock data to Groq and return a natural language summary."""
    prompt = format_stock_prompt(stock_data)

    completion = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role": "system", "content": "You are a helpful financial assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.6,
        max_tokens=300,
        top_p=1,
        stream=True
    )

    response_text = ""
    for chunk in completion:
        content = getattr(chunk.choices[0].delta, "content", None)
        if content:
            response_text += content

    return response_text.strip()

def get_stock_info(symbol):
    """Unified stock summary with Groq AI-enhanced natural language output."""
    try:
        if is_valid_stock_yf(symbol):
            stock = yf.Ticker(symbol)
            data = stock.history(period="1d")
            if not data.empty:
                row = data.iloc[-1]
                stock_data = {
                    "source": "Yahoo Finance",
                    "symbol": symbol,
                    "date": row.name.strftime("%Y-%m-%d"),
                    "open": f"{row['Open']:.2f}",
                    "high": f"{row['High']:.2f}",
                    "low": f"{row['Low']:.2f}",
                    "close": f"{row['Close']:.2f}",
                    "volume": f"{int(row['Volume']):,}"
                }
                return get_natural_stock_response(stock_data)

        # Fallback to Alpha Vantage
        alpha_data = get_stock_info_alpha(symbol)
        if alpha_data and not alpha_data.get("error"):
            return get_natural_stock_response(alpha_data)

        error_msg = alpha_data.get("message") if isinstance(alpha_data, dict) else "Unknown error"
        return f"⚠ Sorry, I couldn’t retrieve data for '{symbol}'. Reason: {error_msg}"

    except Exception as e:
        return f"❌ Error while fetching stock data for '{symbol}': {str(e)}"


# For test run
if __name__ == "__main__":
    n=input("Enter:")
    get_stock_info(n)
    # print(get_stock_info("TCS.NS"))
