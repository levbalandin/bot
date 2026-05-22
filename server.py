```python
from flask import Flask, request
import requests

app = Flask(__name__)

# ================= CONFIG =================

BOT_TOKEN = "8685106379:AAET5pcVkmw9uuceDCMllFX_hwRgOguTsTI"

TRIBUTE_URL = "https://t.me/tribute/app?startapp=sViL"

# ================= SEND =================

def send(chat_id, text, keyboard=None):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        data["reply_markup"] = keyboard

    try:
        requests.post(url, json=data, timeout=10)
    except:
        pass

# ================= TELEGRAM =================

@app.route("/telegram", methods=["POST"])
def telegram():

    update = request.get_json()

    if not update:
        return "ok"

    # ================= MESSAGE =================

    if "message" in update:

        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text == "/start":

            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "💳 ОПЛАТИТЬ ПОДПИСКУ",
                            "url": TRIBUTE_URL
                        }
                    ]
                ]
            }

            send(
                chat_id,
                "💎 Оформи подписку через Tribute:",
                keyboard
            )

    return "ok"

# ================= HOME =================

@app.route("/")
def home():
    return "BOT WORKING"

# ================= SET WEBHOOK =================

@app.route("/setwebhook")
def set_webhook():

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        json={
            "url": "https://bot-lp4u.onrender.com/telegram"
        }
    )

    return "ok"

# ================= RUN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
```
