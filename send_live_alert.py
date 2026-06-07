import os
import json
import requests

BOT = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT = os.environ.get("TELEGRAM_CHAT_ID")


def send(msg):
    url = f"https://api.telegram.org/bot{BOT}/sendMessage"

    requests.post(url, data={
        "chat_id": CHAT,
        "text": msg,
        "parse_mode": "HTML"
    })


def main():
    try:
        with open("data/live_signal.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        return

    stock = data["stock"]

    msg = f"""
🚨 <b>تنبيه اختراق LIVE</b>

📊 {stock['name']} - {stock['symbol']}

💰 السعر: {stock['price']}
🎯 مقاومة: {stock['resistance']}

🔥 حجم: {round(data['vol_ratio'],2)}x
📈 Score: {data['score']}

⚡ فرصة زخم قوية
"""

    send(msg)


if __name__ == "__main__":
    main()
