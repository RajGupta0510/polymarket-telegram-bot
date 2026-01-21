import requests
import time
from datetime import datetime, timezone

# =====================
# TELEGRAM DETAILS
# =====================

BOT_TOKEN = "8489375950:AAG9i5uoKFA4XgtwHwDN9BgO2ws23uwmoh4"
CHAT_ID = 1849671800

# =====================
# POLYMARKET SETTINGS
# =====================

POLYMARKET_API = "https://data-api.polymarket.com/trades?limit=100"
CHECK_INTERVAL = 5
MIN_TRADE_USD = 0

last_seen_timestamp = 0

# =====================
# TELEGRAM FUNCTION
# =====================

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, json=data)

# =====================
# MAIN LOOP
# =====================

send_message("Polymarket trade bot is now running.")

while True:
    try:
        trades = requests.get(POLYMARKET_API).json()

        for trade in trades:
            timestamp = trade.get("timestamp", 0)
            if timestamp <= last_seen_timestamp:
                continue

            market = trade.get("title", "Unknown Prediction")
            side = trade.get("side", "UNKNOWN")
            price = float(trade.get("price", 0))
            size = float(trade.get("size", 0))
            value = price * size

            slug = trade.get("slug") or trade.get("market_slug")
            link = f"https://polymarket.com/market/{slug}" if slug else "https://polymarket.com"

            time_utc = datetime.fromtimestamp(
                timestamp, timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S UTC")

            if value < MIN_TRADE_USD:
                last_seen_timestamp = max(last_seen_timestamp, timestamp)
                continue

            msg = (
                "POLYMARKET TRADE\n\n"
                f"Prediction: {market}\n"
                f"Side: {side}\n"
                f"Price: ${price}\n"
                f"Size: {int(size)} shares\n"
                f"Value: ${value:,.2f}\n"
                f"Time: {time_utc}\n\n"
                f"Trade here:\n{link}"
            )

            send_message(msg)
            last_seen_timestamp = max(last_seen_timestamp, timestamp)

    except Exception as e:
        print("Error:", e)

    time.sleep(CHECK_INTERVAL)

    
