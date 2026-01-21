import os
import time
import requests
from datetime import datetime, timezone

# =====================
# TELEGRAM CONFIG
# =====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

# =====================
# POLYMARKET CONFIG
# =====================

POLYMARKET_TRADES_API = "https://data-api.polymarket.com/trades?limit=100"
POLYMARKET_MARKETS_API = "https://data-api.polymarket.com/markets?limit=50"

CHECK_INTERVAL = 5
MIN_TRADE_USD = 500  # 🔥 MIN USD ALERT

last_seen_timestamp = 0
last_update_id = 0

# =====================
# TELEGRAM FUNCTIONS
# =====================

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

# =====================
# /price COMMAND
# =====================

def handle_price_command():
    try:
        markets = requests.get(POLYMARKET_MARKETS_API).json()
        messages = []

        for m in markets:
            title = m.get("title")
            yes_price = m.get("yes_price")
            no_price = m.get("no_price")
            slug = m.get("slug")

            if not title or yes_price is None or no_price is None:
                continue

            link = f"https://polymarket.com/market/{slug}"

            messages.append(
                f"{title}\nYES: {yes_price} | NO: {no_price}\n{link}"
            )

        if messages:
            send_message("POLYMARKET PRICES\n\n" + "\n\n".join(messages[:5]))
        else:
            send_message("No Polymarket prices found.")

    except Exception as e:
        send_message(f"Error fetching prices: {e}")

# =====================
# STARTUP MESSAGE
# =====================

send_message("Polymarket trade bot is now running.")

# =====================
# MAIN LOOP
# =====================

while True:
    try:
        # -------- TELEGRAM COMMANDS --------
        updates = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}"
        ).json()

        for u in updates.get("result", []):
            last_update_id = u["update_id"]
            text = u.get("message", {}).get("text", "")

            if text == "/price":
                handle_price_command()

        # -------- POLYMARKET TRADES --------
        trades = requests.get(POLYMARKET_TRADES_API).json()

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

