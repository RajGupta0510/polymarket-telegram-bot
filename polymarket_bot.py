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
POLYMARKET_MARKETS_API = "https://data-api.polymarket.com/markets?limit=200"

CHECK_INTERVAL = 5   # seconds (near real-time)

MIN_TRADE_USD = 500        # 🔥 whale filter
MAX_PRICE_ALERT = 0.60     # 🔥 max price filter (60 cents)

# =====================
# STATE (MODE 1)
# =====================

last_update_id = 0
seen_trades = set()
market_cache = {}

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
# MARKET LIVE TIME
# =====================

def fetch_market_live_time(slug):
    if not slug:
        return "Not Provided by API"

    if slug in market_cache:
        return market_cache[slug]

    try:
        url = f"https://data-api.polymarket.com/markets/{slug}"
        res = requests.get(url, timeout=10).json()

        created = (
            res.get("created_at")
            or res.get("createdAt")
            or res.get("start_date")
            or res.get("startDate")
            or res.get("created_time")
        )

        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except:
                try:
                    dt = datetime.fromtimestamp(float(created), timezone.utc)
                except:
                    market_cache[slug] = "Not Provided by API"
                    return "Not Provided by API"

            dt_ist = dt.astimezone(IST).strftime("%d %b %Y %I:%M %p IST")
            market_cache[slug] = dt_ist
            return dt_ist

    except:
        pass

    market_cache[slug] = "Not Provided by API"
    return "Not Provided by API"

# =====================
# TELEGRAM COMMANDS
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
                ["vs", "match", "final", "league", "cup", "open"],
                "🏟️ SPORTS MARKETS"
            )

        elif text.startswith("/nba"):
            send_category_markets(
                ["nba", "lakers", "warriors", "celtics", "bucks", "heat", "nets"],
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
                ["war", "conflict", "china", "taiwan", "russia", "ukraine", "israel", "iran"],
                "🌍 GEOPOLITICS MARKETS"
            )

# =====================
# MARKET COMMAND FUNCTIONS
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
            f"YES: {int(yes_price * 100)}¢\n"
            f"{link}\n\n"
        )

        count += 1
        if count >= 6:
            break

    if count == 0:
        msg += "No matching price markets found under filters."

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
        if yes_price is None or yes_price > MAX_PRICE_ALERT:
            continue

        slug = market.get("slug")
        link = f"https://polymarket.com/market/{slug}"

        msg += (
            f"{title}\n"
            f"YES: {int(yes_price * 100)}¢\n"
            f"{link}\n\n"
        )

        count += 1
        if count >= 6:
            break

    if count == 0:
        msg += "No matching markets found under filters."

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

            # 🔥 Price filter
            if price > MAX_PRICE_ALERT:
                continue

            # 🔥 USD whale filter
            if value < MIN_TRADE_USD:
                continue

            trade_id = (
                f"{timestamp}-"
                f"{trade.get('slug')}-"
                f"{trade.get('side')}-"
                f"{price}-"
                f"{size}"
            )

            # ✅ MODE 1 DEDUP
            if trade_id in seen_trades:
                continue

            title = trade.get("title", "Unknown Market")

            # Position logic (sports + yes/no support)
            side_raw = trade.get("side", "").upper()
            position = trade.get("outcome") or ("YES" if side_raw == "BUY" else "NO")

            slug = trade.get("slug") or trade.get("market_slug")
            link = f"https://polymarket.com/market/{slug}"

            trade_time_ist = datetime.fromtimestamp(
                timestamp, IST
            ).strftime("%d %b %Y %I:%M %p IST")

            market_live = fetch_market_live_time(slug)

            msg = (
                "📢 POLYMARKET TRADE ALERT\n\n"
                f"Market: {title}\n"
                f"Position: {position}\n"
                f"Price: ${round(price,4)}\n"
                f"Size: {int(size)} shares\n"
                f"Value: ${value:,.2f}\n"
                f"Market Live: {market_live}\n"
                f"Trade Time: {trade_time_ist}\n\n"
                f"Trade here:\n{link}"
            )

            send_message(msg)
            seen_trades.add(trade_id)

    except Exception as e:
        print("Error:", e)

    time.sleep(CHECK_INTERVAL)
