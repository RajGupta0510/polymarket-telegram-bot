import os
import time
import requests
from datetime import datetime, timezone, timedelta

# =========================
# TELEGRAM CONFIG (ENV)
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

# =========================
# POLYMARKET CONFIG
# =========================

POLYMARKET_TRADES_API = "https://data-api.polymarket.com/trades?limit=100"

CHECK_INTERVAL = 2          # ⏱ FASTEST SAFE POLLING
MIN_TRADE_USD = 20           # 🔧 CHANGE THIS AS NEEDED

last_seen_timestamp = 0

# =========================
# TELEGRAM FUNCTION
# =========================

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload, timeout=10)

# =========================
# START MESSAGE
# =========================

send_message("✅ Polymarket trade bot is now running.")

# =========================
# MAIN LOOP
# =========================

while True:
    try:
        response = requests.get(POLYMARKET_TRADES_API, timeout=10)
        trades = response.json()

        # 🔥 ENSURE NEWEST DATA ORDER
        trades = sorted(trades, key=lambda x: x.get("timestamp", 0))

        for trade in trades:
            timestamp = trade.get("timestamp", 0)

            if timestamp <= last_seen_timestamp:
                continue

            # -------- MARKET INFO --------
            market = trade.get("title", "Unknown Prediction")

            outcome_raw = trade.get("outcome", "")
            outcome = outcome_raw.upper() if isinstance(outcome_raw, str) else "UNKNOWN"

            if outcome not in ["YES", "NO"]:
                last_seen_timestamp = max(last_seen_timestamp, timestamp)
                continue

            price = float(trade.get("price", 0))
            size = float(trade.get("size", 0))
            value = price * size

            # -------- MIN USD FILTER --------
            if value < MIN_TRADE_USD:
                last_seen_timestamp = max(last_seen_timestamp, timestamp)
                continue

            # -------- MARKET LINK --------
            slug = trade.get("slug") or trade.get("market_slug")
            link = f"https://polymarket.com/market/{slug}" if slug else "https://polymarket.com"

            # -------- IST TIME (12H FORMAT) --------
            ist = timezone(timedelta(hours=5, minutes=30))
            time_ist = datetime.fromtimestamp(
                timestamp, ist
            ).strftime("%Y-%m-%d %I:%M:%S %p IST")

            # -------- MESSAGE --------
            message = (
                "📊 POLYMARKET TRADE\n\n"
                f"Prediction: {market}\n"
                f"Outcome: {outcome}\n"
                f"Price: ${price}\n"
                f"Size: {int(size)} shares\n"
                f"Value: ${value:,.2f}\n"
                f"Time: {time_ist}\n\n"
                f"Trade here:\n{link}"
            )

            send_message(message)

            last_seen_timestamp = max(last_seen_timestamp, timestamp)

    except Exception as e:
        print("Error:", e)

    time.sleep(CHECK_INTERVAL)

