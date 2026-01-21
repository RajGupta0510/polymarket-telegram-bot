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
MIN_TRADE_USD = 20   # 🔧 CHANGE WHEN NEEDED

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
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload, timeout=10)


def handle_commands():
    global last_update_id

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 10}
    data = requests.get(url, params=params, timeout=15).json()

    for update in data.get("result", []):
        last_update_id = update["update_id"]
        msg = update.get("message", {})
        text = msg.get("text", "").lower().strip()
        chat_id = msg.get("chat", {}).get("id")

        if chat_id != CHAT_ID:
            continue

        if text.startswith("/price"):
            send_price_markets()

        elif text.startswith("/sports"):
            send_category_markets(
                ["win", "match", "vs", "final", "league", "cup", "score"],
                "🏟️ SPORTS MARKETS"
            )

        elif text.startswith("/nba"):
            send_category_markets(
                ["nba", "lakers", "warriors", "celtics", "bucks", "playoffs"],
                "🏀 NBA MARKETS"
            )

        elif text.startswith("/ufc"):
            send_category_markets(
                ["ufc", "fight", "knockout", "submission", "round"],
                "🥊 UFC MARKETS"
            )

        elif text.startswith("/cricket"):
            send_category_markets(
                ["cricket", "ipl", "odi", "t20", "test", "world cup"],
                "🏏 CRICKET MARKETS"
            )

        elif text.startswith("/geopolitics"):
            send_category_markets(
                ["war", "conflict", "china", "taiwan", "russia",
                 "ukraine", "israel", "iran"],
                "🌍 GEOPOLITICS MARKETS"
            )


# =====================
# MARKET COMMAND HELPERS
# =====================

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

        slug = market.get("slug")
        link = f"https://polymarket.com/market/{slug}"

        msg += f"{title}\nYES: {int(yes_price * 100)}%\n{link}\n\n"
        count += 1

        if count >= 6:
            break

    send_message(msg.strip())


def send_category_markets(keywords, header):
    res = requests.get(POLYMARKET_MARKETS_API, timeout=15).json()

    msg = f"{header}\n\n"
    count = 0

    for market in res:
        title = market.get("title", "")
        title_lower = title.lower()

        if not any(k in title_lower for k in keywords):
            continue

        outcomes = market.get("outcomes", [])
        if not outcomes:
            continue

        yes_price = outcomes[0].get("price")
        if yes_price is None:
            continue

        slug = market.get("slug")
        link = f"https://polymarket.com/market/{slug}"

        msg += f"{title}\nYES: {int(yes_price * 100)}%\n{link}\n\n"
        count += 1

        if count >= 6:
            break

    send_message(msg.strip())

# =====================
# STARTUP MESSAGE
# =====================

send_message("✅ Polymarket trade bot is now running.")

# =====================
# MAIN LOOP (UNCHANGED)
# =====================

while True:
    try:
        handle_commands()

        trades = requests.get(POLYMARKET_TRADES_API, timeout=15).json()

        for trade in trades:
            timestamp = trade.get("timestamp", 0)

            # ✅ TIMESTAMP FIX
            if timestamp < last_seen_timestamp:
                continue

            price = float(trade.get("price", 0))
            size = float(trade.get("size", 0))
            value = price * size

            # ✅ USD TOLERANCE
            if value + 1 < MIN_TRADE_USD:
                continue

            side_raw = trade.get("side", "").upper()
            side = "YES" if side_raw == "BUY" else "NO" if side_raw == "SELL" else "UNKNOWN"

            title = trade.get("title", "Unknown Prediction")
            slug = trade.get("slug") or trade.get("market_slug")
            link = f"https://polymarket.com/market/{slug}" if slug else "https://polymarket.com"

            time_ist = datetime.fromtimestamp(
                timestamp, IST
            ).strftime("%d %b %Y %I:%M %p IST")

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
