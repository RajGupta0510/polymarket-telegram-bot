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

MIN_TRADE_USD = 500        # whale filter
MAX_PRICE_ALERT = 0.60     # price filter (60 cents)

# =====================
# STATE (MODE 1)
# =====================

last_update_id = 0
seen_trades = set()
market_cache = {}   # slug -> created_time

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

# =====================
# MARKET HELPERS
# =====================

def fetch_market_live_time(slug):
    """
    Fetch market creation time from Polymarket and cache it.
    """
    if slug in market_cache:
        return market_cache[slug]

    try:
        res = requests.get(POLYMARKET_MARKETS_API, timeout=10).json()
        for market in res:
            if market.get("slug") == slug:
                created = (
                    market.get("created_at")
                    or market.get("createdAt")
                    or market.get("created_time")
                    or market.get("start_date")
                )

                if created:
                    # handle ISO format
                    try:
                        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    except:
                        dt = datetime.fromtimestamp(float(created), timezone.utc)

                    dt_ist = dt.astimezone(IST).strftime("%d %b %Y %I:%M %p IST")
                    market_cache[slug] = dt_ist
                    return dt_ist
    except:
        pass

    market_cache[slug] = "Unknown"
    return "Unknown"

# =====================
# COMMAND HANDLER
# =====================

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
                ["vs", "match", "final", "league", "cup", "open", "tournament"],
                "🏟️ SPORTS MARKETS"
            )

        elif text.startswith("/nba"):
            send_category_markets(
                ["nba", "lakers", "warriors", "celtics", "bucks"],
                "🏀 NBA MARKETS"
            )

        elif text.startswith("/ufc"):
            send_category_markets(
                ["ufc", "fight", "knockout", "submission"],
                "🥊 UFC MARKETS"
            )

        elif text.startswith("/cricket"):
            send_category_markets(
                ["cricket", "ipl", "odi", "t20", "test"],
                "🏏 CRICKET MARKETS"
            )

        elif text.startswith("/geopolitics"):
            send_category_markets(
                ["war", "conflict", "china", "taiwan",
                 "russia", "ukraine", "israel", "iran"],
                "🌍 GEOPOLITICS MARKETS"
            )

# =====================
# MARKET COMMANDS
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
        if yes_price is None or yes_price > MAX_PRICE_ALERT:
            continue

        slug = market.get("slug")
        link = f"https://polymarket.com/market/{slug}"

        msg += (
            f"{title}\n"
            f"YES: {int(yes_price * 100)}%\n"
            f"{link}\n\n"
        )

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

        price = outcomes[0].get("price")
        if price is None or price > MAX_PRICE_ALERT:
            continue

        slug = market.get("slug")
        link = f"https://polymarket.com/market/{slug}"

        msg += (
            f"{title}\n"
            f"YES: {int(price * 100)}%\n"
            f"{link}\n\n"
        )

        count += 1
        if count >= 6:
            break

    send_message(msg.strip())

# =====================
# STARTUP
# =====================

send_message("🚀 Polymarket AI Trade Bot is LIVE")

# =====================
# MAIN LOOP (MODE 1)
# =====================

while True:
    try:
        handle_commands()

        trades = requests.get(POLYMARKET_TRADES_API, timeout=15).json()

        for trade in trades:
            timestamp = trade.get("timestamp")
            price = float(trade.get("price", 0))
            size = float(trade.get("size", 0))
            value = price * size

            # PRICE FILTER
            if price > MAX_PRICE_ALERT:
                continue

            # USD FILTER
            if value < MIN_TRADE_USD:
                continue

            trade_id = (
                f"{timestamp}-"
                f"{trade.get('slug')}-"
                f"{trade.get('side')}-"
                f"{price}-"
                f"{size}"
            )

            # MODE 1 DEDUP
            if trade_id in seen_trades:
                continue

            title = trade.get("title", "Unknown Market")
            slug = trade.get("slug") or trade.get("market_slug")
            link = f"https://polymarket.com/market/{slug}"

            outcomes = trade.get("outcomes")

            # SMART POSITION LOGIC
            position = None
            side_raw = trade.get("side", "").upper()

            if outcomes and isinstance(outcomes, list) and len(outcomes) >= 2:
                if side_raw == "BUY":
                    position = outcomes[0].get("name")
                else:
                    position = outcomes[1].get("name")
            else:
                position = "YES" if side_raw == "BUY" else "NO"

            # TIMES
            trade_time = datetime.fromtimestamp(
                timestamp, IST
            ).strftime("%d %b %Y %I:%M %p IST")

            market_live = fetch_market_live_time(slug)

            msg = (
                "📢 POLYMARKET TRADE ALERT\n\n"
                f"Market: {title}\n"
                f"Position: {position}\n"
                f"Price: ${price}\n"
                f"Size: {int(size)} shares\n"
                f"Value: ${value:,.2f}\n"
                f"Market Live: {market_live}\n"
                f"Trade Time: {trade_time}\n\n"
                f"Trade here:\n{link}"
            )

            send_message(msg)
            seen_trades.add(trade_id)

    except Exception as e:
        print("Error:", e)

    time.sleep(CHECK_INTERVAL)
