from flask import Flask, request
import stripe
import os
import threading
import time
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

app = Flask(__name__)

# ---------------- TELEGRAM ----------------
BOT_TOKEN = "YOUR_BOT_TOKEN"
CHANNEL_ID = -1003830259549

# ---------------- STRIPE ----------------
STRIPE_SECRET = "YOUR_STRIPE_SECRET"
STRIPE_WEBHOOK_SECRET = "YOUR_STRIPE_WEBHOOK_SECRET"

stripe.api_key = STRIPE_SECRET

# ---------------- ТАРИФЫ ----------------
PRICE_MAP = {
    "1m": "price_xxx1",
    "3m": "price_xxx2",
    "6m": "price_xxx3",
    "12m": "price_xxx4"
}

# ---------------- ДАННЫЕ ----------------
user_subscriptions = {}

# ---------------- TELEGRAM APP ----------------
bot_app = Application.builder().token(BOT_TOKEN).build()


# ---------------- START ----------------
async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("💳 1 месяц", callback_data="1m")],
        [InlineKeyboardButton("💳 3 месяца", callback_data="3m")],
        [InlineKeyboardButton("💳 6 месяцев", callback_data="6m")],
        [InlineKeyboardButton("💳 12 месяцев", callback_data="12m")]
    ]

    await update.message.reply_text(
        "Выбери тариф:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------------- CALLBACK ----------------
async def choose_plan(update: Update, context):
    query = update.callback_query
    await query.answer()

    plan = query.data
    price_id = PRICE_MAP[plan]
    user_id = query.from_user.id

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{
            "price": price_id,
            "quantity": 1
        }],
        success_url="https://t.me/",
        metadata={
            "telegram_id": str(user_id),
            "price_id": price_id
        }
    )

    await query.message.reply_text(
        "Оплати:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 ОПЛАТИТЬ", url=session.url)]
        ])
    )


# ---------------- ACCESS ----------------
def send_access(user_id, days):
    expire = datetime.now() + timedelta(days=days)
    user_subscriptions[user_id] = expire
    print("ACCESS:", user_id, expire)


# ---------------- STRIPE WEBHOOK ----------------
@app.route("/stripe", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print("Stripe error:", e)
        return "error", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        metadata = session.get("metadata", {})
        user_id = metadata.get("telegram_id")
        price_id = metadata.get("price_id")

        if user_id and price_id:
            if price_id == PRICE_MAP["1m"]:
                days = 30
            elif price_id == PRICE_MAP["3m"]:
                days = 90
            elif price_id == PRICE_MAP["6m"]:
                days = 180
            elif price_id == PRICE_MAP["12m"]:
                days = 365
            else:
                days = 0

            if days:
                send_access(int(user_id), days)

    return "ok", 200


# ---------------- TELEGRAM WEBHOOK ----------------
@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json(force=True)

        update = Update.de_json(data, bot_app.bot)

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_app.process_update(update))

        return "ok"

    except Exception as e:
        print("TELEGRAM ERROR:", e)
        return "error", 200


# ---------------- CHECK EXPIRED ----------------
def check_expired():
    while True:
        now = datetime.now()

        for user_id, expire in list(user_subscriptions.items()):
            if now > expire:
                try:
                    bot_app.bot.ban_chat_member(CHANNEL_ID, user_id)
                    bot_app.bot.unban_chat_member(CHANNEL_ID, user_id)
                    del user_subscriptions[user_id]
                    print("REMOVED:", user_id)
                except Exception as e:
                    print("ERROR:", e)

        time.sleep(60)


# ---------------- SETUP BOT ----------------
def setup_bot():
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(choose_plan))


# ---------------- HOME ----------------
@app.route("/")
def home():
    return "server running"


# ---------------- START ----------------
if __name__ == "__main__":
    setup_bot()

    threading.Thread(target=check_expired, daemon=True).start()

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
