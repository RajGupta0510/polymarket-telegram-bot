import os
import time
import requests
from datetime import datetime, timezone, timedelta

# =====================
# TELEGRAM CONFIG
# =====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

# =====================
# POLYMARKET CONFIG
# =====================

POLYMARKET_TRADES_API = "https://data-api.polymarket.com/trades?limit=500"
POLYMARKET_MARKETS_API = "https://data-api.polymarket.com/markets?limit=100"

CHECK_INTERVAL = 5
MIN_TRADE_USD = 100   # 🔥 CHANGE THIS ANYTIME

# =====================
# STATE
# =====================

last_seen_timestamp = 0
last_update_id = 0

IST = timezone(timedelta(hours=5, minutes=30))

# =====================
# TELEGRAM HELPERS
# =====================

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}
    requests.post(url, json=payload, timeout=10)


def handle_commands():
    global last_update_id

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 10}
    data = requests.get(url, params=params, timeout=15).json()

    for update in data.get("result", []):
        last_update_id = update["update_id"]
        msg = update.get("message", {})
        text = msg.get("text", "")
        chat_id = msg.get("chat", {}).get("id")

        if chat_id != CHAT_ID:
            continue

        if text.lower().startswith("/price"):
            send_price_markets()


def send_price_markets():
    res = requests.get(POLYMARKET_MARKETS_API, timeout=15).json()

    msg = "📊 POLYMARKET PRICE MARKETS\n\n"
    count = 0

    for market in res:
        title = market.get("title", "")
        if "price" not in title.lower():
            continue

        outcomes = market.get("outcomes", [])
        if not outcomes:
            continue

        yes_price = outcomes[0].get("price")
        if yes_price is None:
            continue

        msg += f"{title}\nYES: {int(yes_price * 100)}%\n\n"
        count += 1

        if count >= 6:
            break

    send_message(msg.strip())

# =====================
# STARTUP MESSAGE
# =====================

send_message("✅ Polymarket trade bot is now running.")

# =====================
# MAIN LOOP
# =====================

while True:
    try:
        handle_commands()

        trades = requests.get(POLYMARKET_TRADES_API, timeout=15).json()

        for trade in trades:
            timestamp = trade.get("timestamp", 0)

            # ✅ TIMESTAMP SKIP FIX
            if timestamp < last_seen_timestamp:
                continue

            price = float(trade.get("price", 0))
            size = float(trade.get("size", 0))
            value = price * size

            # ✅ USD TOLERANCE FIX
            if value + 1 < MIN_TRADE_USD:
                continue

            side_raw = trade.get("side", "").upper()
            if side_raw == "BUY":
                side = "YES"
            elif side_raw == "SELL":
                side = "NO"
            else:
                side = "UNKNOWN"

            title = trade.get("title", "Unknown Prediction")
            slug = trade.get("slug") or trade.get("market_slug")
            link = f"https://polymarket.com/market/{slug}" if slug else "https://polymarket.com"

            time_ist = datetime.fromtimestamp(timestamp, IST).strftime(
                "%d %b %Y %I:%M %p IST"
            )

            msg = (
                "📢 POLYMARKET TRADE\n\n"
                f"Prediction: {title}\n"
                f"Side: {side}\n"
                f"Price: ${price}\n"
                f"Size: {int(size)} shares\n"
                f"Value: ${value:,.2f}\n"
                f"Time: {time_ist}\n\n"
                f"Trade here:\n{link}"
            )

            send_message(msg)

            last_seen_timestamp = max(last_seen_timestamp, timestamp)

    except Exception as e:
        print("Error:", e)

    time.sleep(CHECK_INTERVAL)



