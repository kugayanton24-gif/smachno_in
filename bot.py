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


# ================== ENV ==================
TOKEN = os.getenv("TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

UA_TZ = ZoneInfo("Europe/Kyiv")


# ================== ADMIN ==================
ADMIN_ID = 890221392
BTN_ADMIN = "📨 Розсилка афіші"


# ================== UI ==================
BTN_CONTACT = "📲 Поділитися контактом"
BTN_LOYALTY = "💳 Система лояльності"

START_TEXT = "Smachno In — смачно, швидко, твоє 🤍"

LOYALTY_LINK = "https://loyal.ws/d/699f33dd647328c6f9249a9f/echopoolclub"


# ================== GOOGLE SHEETS ==================
def get_sheet():
    creds = json.loads(GOOGLE_CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_info(creds, scopes=scopes)
    gc = gspread.authorize(credentials)
    return gc.open_by_key(SHEET_ID).sheet1


def ensure_header(ws):
    if not ws.get_all_values():
        ws.append_row([
            "datetime",
            "first_name",
            "last_name",
            "phone",
            "username",
            "user_id"
        ])


def save_contact(user, phone):
    ws = get_sheet()
    ensure_header(ws)

    dt = datetime.now(UA_TZ).strftime("%d.%m.%Y %H:%M:%S")

    ws.append_row([
        dt,
        user.first_name or "",
        user.last_name or "",
        phone,
        user.username or "",
        str(user.id)
    ])


def get_all_user_ids():
    ws = get_sheet()
    rows = ws.get_all_values()

    users = []
    for r in rows:
        if len(r) >= 6:
            try:
                uid = int(r[5])
                users.append(uid)
            except:
                continue
    return list(set(users))


def user_exists(user_id):
    return user_id in get_all_user_ids()


# ================== KEYBOARDS ==================
def kb_contact():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_CONTACT, request_contact=True)]],
        resize_keyboard=True
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


# ================== HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # адмін одразу в меню
    if user.id == ADMIN_ID:
        await update.message.reply_text(
            START_TEXT,
            reply_markup=kb_main(user.id)
        )
        return

    await update.message.reply_text(START_TEXT)

    # якщо нема в таблиці — просимо контакт
    if not user_exists(user.id):
        await update.message.reply_text(
            "Щоб продовжити — поділись контактом 👇",
            reply_markup=kb_contact()
        )
    else:
        await update.message.reply_text(
            "Ти вже в системі 🤍",
            reply_markup=kb_main(user.id)
        )


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    phone = update.message.contact.phone_number

    save_contact(user, phone)

    await update.message.reply_text(
        "Дякуємо 🤍",
        reply_markup=kb_main(user.id)
    )


async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = (update.message.text or "").strip()

    # ========= БЛОКУЄМО БЕЗ КОНТАКТУ =========
    if user.id != ADMIN_ID and not user_exists(user.id):
        await update.message.reply_text(
            "Спочатку поділись контактом 👇",
            reply_markup=kb_contact()
        )
        return

    # ========= АДМІН РОЗСИЛКА =========
    if msg == BTN_ADMIN and user.id == ADMIN_ID:
        context.user_data["step"] = "photo"
        await update.message.reply_text(
            "Надішли фото афіші",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    if user.id == ADMIN_ID:
        step = context.user_data.get("step")

        if step == "photo":
            if not update.message.photo:
                await update.message.reply_text("Потрібно фото")
                return

            context.user_data["photo"] = update.message.photo[-1].file_id
            context.user_data["step"] = "text"

            await update.message.reply_text("Тепер надішли текст")
            return

        elif step == "text":
            users = get_all_user_ids()
            photo = context.user_data.get("photo")
            caption = msg

            await update.message.reply_text(f"Розсилка: {len(users)}")

            ok, fail = 0, 0

            for uid in users:
                try:
                    await context.bot.send_photo(uid, photo, caption=caption)
                    ok += 1
                except:
                    fail += 1

            context.user_data.clear()

            await update.message.reply_text(
                f"Готово ✅\nOK: {ok}\nFail: {fail}",
                reply_markup=kb_main(user.id)
            )
            return

    # ========= ЗВИЧАЙНИЙ КОРИСТУВАЧ =========
    if msg == BTN_LOYALTY:
        await update.message.reply_text(
            "Натисни кнопку нижче 👇",
            reply_markup=inline_loyalty()
        )


# ================== MAIN ==================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, contact))
    app.add_handler(MessageHandler(filters.PHOTO, text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

    app.run_polling()


if __name__ == "__main__":
    main()
