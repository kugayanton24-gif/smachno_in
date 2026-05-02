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
BTN_ADMIN_BROADCAST = "📨 Розсилка афіші"


# ================== BUTTONS ==================
BTN_LOYALTY = "💳 Система лояльності"
BTN_SHARE_CONTACT = "📲 Поділитися контактом"


# ================== LINK ==================
LOYALTY_LINK = "https://loyal.ws/d/699f33dd647328c6f9249a9f/echopoolclub"


# ================== TEXT ==================
START_TEXT = "Smachno In — смачно, швидко, твоє 🤍"

TEXT_LOYALTY = (
    "Ставайте частиною програми лояльності Smachno In 🤍\n\n"
    "— кешбек з кожного замовлення\n"
    "— персональні пропозиції\n\n"
    "Натисніть кнопку нижче ⬇️"
)


# ================== GOOGLE SHEETS ==================
def get_sheet():
    creds_dict = json.loads(GOOGLE_CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID).sheet1


def ensure_header(ws):
    values = ws.get_all_values()
    if not values:
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
        phone or "",
        user.username or "",
        str(user.id)
    ])


# ================== USERS FROM SHEET ==================
def get_all_user_ids():
    ws = get_sheet()
    rows = ws.get_all_values()

    users = []
    seen = set()

    for r in rows:
        if len(r) < 6:
            continue

        val = str(r[5]).strip()

        if not val or val.lower() in ["user_id", "id"]:
            continue

        try:
            uid = int(val)
            if uid not in seen:
                seen.add(uid)
                users.append(uid)
        except:
            continue

    return users


# ================== KEYBOARDS ==================
def kb_contact():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_SHARE_CONTACT, request_contact=True)]],
        resize_keyboard=True
    )


def kb_main(user_id):
    keyboard = [
        [KeyboardButton(BTN_LOYALTY)]
    ]

    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton(BTN_ADMIN_BROADCAST)])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def inline_loyalty():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Перейти", url=LOYALTY_LINK)]
    ])


# ================== HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # адмін без контакту
    if user.id == ADMIN_ID:
        context.user_data["contact_saved"] = True
        await update.message.reply_text(
            START_TEXT,
            reply_markup=kb_main(user.id)
        )
        return

    context.user_data["contact_saved"] = False

    await update.message.reply_text(
        START_TEXT,
        reply_markup=kb_contact()
    )


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    phone = update.message.contact.phone_number

    save_contact(user, phone)
    context.user_data["contact_saved"] = True

    await update.message.reply_text(
        "Дякуємо 🤍",
        reply_markup=kb_main(user.id)
    )


async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message.text

    # ===== АДМІН РОЗСИЛКА =====
    if msg == BTN_ADMIN_BROADCAST and user.id == ADMIN_ID:
        context.user_data["step"] = "photo"
        await update.message.reply_text(
            "Надішли фото",
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
            await update.message.reply_text("Тепер текст")
            return

        elif step == "text":
            photo = context.user_data.get("photo")
            caption = msg

            users = get_all_user_ids()

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
                f"Готово\nOK: {ok}\nFail: {fail}",
                reply_markup=kb_main(user.id)
            )
            return

    # ===== ЗВИЧАЙНИЙ ЮЗЕР =====
    if not context.user_data.get("contact_saved"):
        await update.message.reply_text(
            "Поділись контактом 👇",
            reply_markup=kb_contact()
        )
        return

    if msg == BTN_LOYALTY:
        await update.message.reply_text(
            TEXT_LOYALTY,
            reply_markup=inline_loyalty()
        )
        return


# ================== MAIN ==================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, contact))
    app.add_handler(MessageHandler(filters.ALL, text))

    app.run_polling()


if __name__ == "__main__":
    main()
