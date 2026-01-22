import os
import requests
import time
from datetime import datetime, timezone, timedelta

# =============================
# TELEGRAM CONFIG
# =============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

# =============================
# POLYMARKET CONFIG
# =============================
POLYMARKET_TRADES_API = "https://data-api.polymarket.com/trades?limit=100"
POLYMARKET_MARKETS_API = "https://data-api.polymarket.com/markets?limit=200"

CHECK_INTERVAL = 5              # seconds
MIN_TRADE_USD = 500             # minimum USD alert
MAX_PRICE_ALERT = 0.60          # max YES/NO price alert

# =============================
# STATE
# =============================
last_seen_timestamp = 0
last_trade_ids = set()

# =============================
# TELEGRAM FUNCTIONS
# =============================

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, json=data)


def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    if offset:
        url += f"?offset={offset}"
    return requests.get(url).json()

# =============================
# TIME UTILS
# =============================

def utc_to_ist(ts):
    ist = timezone(timedelta(hours=5, minutes=30))
    dt = datetime.fromtimestamp(ts, timezone.utc).astimezone(ist)
    return dt.strftime("%d %b %Y %I:%M %p IST")

# =============================
# MARKET SEARCH
# =============================

def search_markets(keyword):
    res = requests.get(POLYMARKET_MARKETS_API).json()
    results = []
    for m in res:
        title = m.get("title", "")
        if keyword.lower() in title.lower():
            results.append(m)
    return results[:15]

# =============================
# COMMAND HANDLER
# =============================

def handle_commands():
    global last_update_id
    updates = get_updates(last_update_id + 1 if 'last_update_id' in globals() else None)

    if not updates.get("result"):
        return

    for u in updates["result"]:
        last_update_id = u["update_id"]
        msg = u.get("message", {})
        text = msg.get("text", "")

        if text.startswith("/price"):
            markets = search_markets("price")
            reply = "📊 PRICE MARKETS (POLYMARKET)\n\n"
            for m in markets:
                title = m.get("title")
                slug = m.get("slug")
                link = f"https://polymarket.com/market/{slug}"
                reply += f"• {title}\n{link}\n\n"
            send_message(reply)

        if text.startswith("/sports"):
            markets = search_markets("vs")
            reply = "🏟 SPORTS MARKETS\n\n"
            for m in markets[:15]:
                title = m.get("title")
                slug = m.get("slug")
                link = f"https://polymarket.com/market/{slug}"
                reply += f"• {title}\n{link}\n\n"
            send_message(reply)

        if text.startswith("/nba"):
            markets = search_markets("NBA")
            send_list("🏀 NBA MARKETS", markets)

        if text.startswith("/ufc"):
            markets = search_markets("UFC")
            send_list("🥊 UFC MARKETS", markets)

        if text.startswith("/cricket"):
            markets = search_markets("Cricket")
            send_list("🏏 CRICKET MARKETS", markets)

        if text.startswith("/geopolitics"):
            markets = search_markets("war")
            send_list("🌍 GEOPOLITICS", markets)


def send_list(title, markets):
    reply = f"{title}\n\n"
    for m in markets[:15]:
        name = m.get("title")
        slug = m.get("slug")
        link = f"https://polymarket.com/market/{slug}"
        reply += f"• {name}\n{link}\n\n"
    send_message(reply)

# =============================
# MAIN LOOP
# =============================

send_message("🚀 Polymarket AI Trade Bot is LIVE")

while True:
    try:
        handle_commands()
        trades = requests.get(POLYMARKET_TRADES_API).json()

        for trade in trades:
            trade_id = trade.get("id")
            if trade_id in last_trade_ids:
                continue

            timestamp = trade.get("timestamp", 0)
            market = trade.get("title", "Unknown Market")
            price = float(trade.get("price", 0))
            size = float(trade.get("size", 0))
            value = price * size

            if value < MIN_TRADE_USD:
                continue

            if price > MAX_PRICE_ALERT:
                continue

            slug = trade.get("slug") or trade.get("market_slug")
            link = f"https://polymarket.com/market/{slug}" if slug else "https://polymarket.com"

            outcome = trade.get("outcome") or trade.get("side")

            # IST Time
            time_ist = utc_to_ist(timestamp)

            msg = (
                "📢 POLYMARKET TRADE ALERT\n\n"
                f"Market: {market}\n"
                f"Position: {outcome}\n"
                f"Price: ${price}\n"
                f"Size: {int(size)} shares\n"
                f"Value: ${value:,.2f}\n"
                f"Time: {time_ist}\n\n"
                f"Trade here:\n{link}"
            )

            send_message(msg)
            last_trade_ids.add(trade_id)

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
