import os
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

TOKEN = os.environ.get("BOT_TOKEN")
DB = "mule_bingo.db"

logging.basicConfig(level=logging.INFO)

def init_db():
    with sqlite3.connect(DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                card_number INTEGER NOT NULL,
                UNIQUE(user_id, card_number)
            )
        """)

def save_user(user):
    with sqlite3.connect(DB) as con:
        con.execute("""
            INSERT INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name
        """, (user.id, user.username, user.full_name))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)

    keyboard = [
        [
            InlineKeyboardButton(
                "🎮 Open Mule Bingo App",
                web_app=WebAppInfo(url="https://mulemuler646.github.io/mule-bingo/")
            )
        ],
        [
            InlineKeyboardButton("👤 Profile", callback_data="profile"),
            InlineKeyboardButton("💰 Balance / Wallet", callback_data="balance"),
        ],
        [
            InlineKeyboardButton("🎱 Play Bingo", callback_data="cards"),
        ],
        [
            InlineKeyboardButton("💳 Deposit", callback_data="deposit"),
            InlineKeyboardButton("💸 Withdraw", callback_data="withdraw"),
        ],
        [
            InlineKeyboardButton("👥 Invite", callback_data="invite"),
            InlineKeyboardButton("🆘 Support", callback_data="support"),
        ],
        [
            InlineKeyboardButton("👥 Group", callback_data="group"),
            InlineKeyboardButton("📜 Rules", callback_data="rules"),
        ],
    ]

    await update.message.reply_text(
        f"🎉 እንኳን ወደ Mule Bingo በደህና መጣህ!\n\n"
        f"ሰላም {user.first_name}!\n"
        "የምትፈልገውን ከታች ምረጥ።",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if query.data == "profile":
        with sqlite3.connect(DB) as con:
            row = con.execute(
                "SELECT balance, created_at FROM users WHERE user_id=?",
                (user.id,)
            ).fetchone()

        await query.edit_message_text(
            f"👤 የእርስዎ ፕሮፋይል\n\n"
            f"ስም: {user.full_name}\n"
            f"Telegram ID: {user.id}\n"
            f"ሂሳብ: {row[0]:.2f} ብር\n"
            f"የተመዘገቡበት: {row[1]}"
        )

    elif query.data == "balance":
        with sqlite3.connect(DB) as con:
            row = con.execute(
                "SELECT balance FROM users WHERE user_id=?",
                (user.id,)
            ).fetchone()
        await query.edit_message_text(
            f"💰 የሂሳብዎ መጠን: {row[0]:.2f} ብር"
        )

    elif query.data == "cards":
        keyboard = [
            [
                InlineKeyboardButton(
                    f"🎱 {n}", callback_data=f"card_{n}"
                )
                for n in range(start, min(start + 5, 201))
            ]
            for start in range(1, 201, 5)
        ]
        await query.edit_message_text(
            "🎱 ከ1–200 ያሉ ካርቴላዎችን ምረጥ።\n"
            "ምርጫህን ለማጠናቀቅ 30 ሰከንድ ይኖርሃል።",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data["selection_open"] = True
        context.user_data["selected_cards"] = set()
        context.job_queue.run_once(
            close_selection, 30, data=user.id,
            name=f"selection_{user.id}"
        )

    elif query.data.startswith("card_"):
        if not context.user_data.get("selection_open"):
            await query.answer("የካርቴላ ምርጫ ጊዜ አልቋል።", show_alert=True)
            return

        number = int(query.data.split("_")[1])
        selected = context.user_data.setdefault("selected_cards", set())

        with sqlite3.connect(DB) as con:
            owner = con.execute(
                "SELECT user_id FROM cards WHERE card_number=?",
                (number,)
            ).fetchone()

            if owner and owner[0] != user.id:
                await query.answer("ይህ ካርቴላ ተይዟል።", show_alert=True)
                return

        if number in selected:
            selected.remove(number)
        else:
            selected.add(number)

        await query.answer(
            f"የመረጥካቸው ካርቴላዎች: {len(selected)}"
        )
    elif query.data == "deposit":
        await query.edit_message_text(
            "💳 ገንዘብ ለማስገባት\n\n"
            "የክፍያ ስርዓቱ ገና አልተገናኘም።"
        )

    elif query.data == "withdraw":
        await query.edit_message_text(
            "💸 ገንዘብ ለማውጣት\n\n"
            "የገንዘብ ማውጫ ስርዓቱ ገና አልተገናኘም።"
        )
    elif query.data == "invite":
        bot = await context.bot.get_me()
        invite_link = f"https://t.me/{bot.username}?start=ref_{user.id}"
        await query.edit_message_text(
            "👥 ጓደኞችህን Mule Bingo እንዲቀላቀሉ ጋብዝ!\\n\\n"
            f"የግብዣ ሊንክህ፦\\n{invite_link}"
        )

    elif query.data == "support":
        await query.edit_message_text(
            "🆘 Support\\n\\n"
            "የSupport ሊንክ ገና አልተዘጋጀም።"
        )

    elif query.data == "group":
        await query.edit_message_text(
            "👥 Mule Bingo Group\\n\\n"
            "የGroup ሊንክ ገና አልተዘጋጀም።"
        )

    elif query.data == "rules":
        await query.edit_message_text(
            "📜 Mule Bingo ህጎች\n\n"
            "• እያንዳንዱ ተጠቃሚ የራሱ ፕሮፋይል ይኖረዋል።\n"
            "• ካርቴላዎች ከ1–200 ይመረጣሉ።\n"
            "• የካርቴላ ምርጫ ጊዜ 30 ሰከንድ ነው።\n"
            "• ክፍያና ሽልማት ከመጀመሩ በፊት ይፋዊ ህጎች ያስፈልጋሉ።"
        )

async def close_selection(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.data
    selected = context.application.user_data.get(user_id, {})
    cards = selected.get("selected_cards", set())

    with sqlite3.connect(DB) as con:
        for number in cards:
            con.execute(
                "INSERT OR IGNORE INTO cards (user_id, card_number) VALUES (?, ?)",
                (user_id, number)
            )

    selected["selection_open"] = False

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="⏰ 30 ሰከንድ አልቋል።\n"
                 f"የመረጥካቸው ካርቴላዎች: {len(cards)}\n"
                 f"{', '.join(map(str, sorted(cards))) if cards else 'ካርቴላ አልመረጥክም።'}"
        )
    except Exception:
        logging.exception("Could not send selection summary")

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN አልተገኘም።")

    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    print("Mule Bingo bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
