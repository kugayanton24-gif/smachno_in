import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import gspread
from google.oauth2.service_account import Credentials


# ================= ENV =================
TOKEN = os.getenv("TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

ADMIN_ID = 890221392
UA_TZ = ZoneInfo("Europe/Kyiv")


# ================= TEXT =================
START_TEXT = "Smachno In — смачно, швидко, твоє 🤍"
BTN_CONTACT = "📲 Поділитися контактом"
BTN_LOYALTY = "💳 Система лояльності"
BTN_ADMIN = "📨 Розсилка афіші"

LOYALTY_LINK = "https://loyal.ws/d/699f33dd647328c6f9249a9f/echopoolclub"


# ================= GOOGLE =================
def get_sheet():
    try:
        creds = json.loads(GOOGLE_CREDS_JSON)
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_info(creds, scopes=scopes)
        gc = gspread.authorize(credentials)
        return gc.open_by_key(SHEET_ID).sheet1
    except Exception as e:
        print("❌ GOOGLE CONNECT ERROR:", e)
        return None


def save_contact(user, phone):
    try:
        ws = get_sheet()
        if not ws:
            print("❌ Sheet not found")
            return

        dt = datetime.now(UA_TZ).strftime("%d.%m.%Y %H:%M:%S")

        ws.append_row([
            dt,
            user.first_name or "",
            user.last_name or "",
            phone or "",
            user.username or "",
            str(user.id)
        ])

        print("✅ SAVED:", user.id)

    except Exception as e:
        print("❌ SAVE ERROR:", e)


def get_users():
    try:
        ws = get_sheet()
        if not ws:
            return []

        rows = ws.get_all_values()

        ids = []
        for r in rows:
            if len(r) >= 6:
                try:
                    ids.append(int(r[5]))
                except:
                    pass

        return list(set(ids))

    except Exception as e:
        print("❌ READ ERROR:", e)
        return []


# ================= KEYBOARDS =================
def kb_contact():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_CONTACT, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def kb_main(user_id):
    kb = [[KeyboardButton(BTN_LOYALTY)]]

    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(BTN_ADMIN)])

    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


def inline_loyalty():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Перейти", url=LOYALTY_LINK)]
    ])


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        START_TEXT + "\n\nПоділись контактом 👇",
        reply_markup=kb_contact()
    )


# ================= CONTACT =================
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    contact = update.message.contact

    # захист
    if contact.user_id != user.id:
        await update.message.reply_text(
            "Надішли свій контакт 👇",
            reply_markup=kb_contact()
        )
        return

    # зберігаємо
    save_contact(user, contact.phone_number)

    # ❗ ВАЖЛИВО — МЕНЮ ВИДАЄМО ЗАВЖДИ
    await update.message.reply_text(
        "Ти в системі 🤍",
        reply_markup=kb_main(user.id)
    )


# ================= TEXT =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    # ===== ЛОЯЛЬНІСТЬ =====
    if text == BTN_LOYALTY:
        await update.message.reply_text(
            "Натисни кнопку 👇",
            reply_markup=inline_loyalty()
        )
        return

    # ===== АДМІН =====
    if user.id == ADMIN_ID:

        if text == BTN_ADMIN:
            context.user_data["step"] = "photo"
            await update.message.reply_text(
                "Надішли фото афіші",
                reply_markup=ReplyKeyboardRemove()
            )
            return

        step = context.user_data.get("step")

        if step == "photo":
            if not update.message.photo:
                await update.message.reply_text("Потрібно фото")
                return

            context.user_data["photo"] = update.message.photo[-1].file_id
            context.user_data["step"] = "text"

            await update.message.reply_text("Тепер текст")
            return

        if step == "text":
            users = get_users()
            photo = context.user_data.get("photo")

            ok, fail = 0, 0

            for uid in users:
                try:
                    await context.bot.send_photo(uid, photo, caption=text)
                    ok += 1
                except Exception as e:
                    print("SEND ERROR:", e)
                    fail += 1

            context.user_data.clear()

            await update.message.reply_text(
                f"Готово\nOK: {ok}\nFail: {fail}",
                reply_markup=kb_main(user.id)
            )
            return


# ================= MAIN =================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.PHOTO, handle_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()


if __name__ == "__main__":
    main()
