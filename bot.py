import os
import datetime
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (ApplicationBuilder, CommandHandler, ContextTypes,
                          MessageHandler, filters, CallbackQueryHandler, ConversationHandler)

LANGUAGE, JOURNAL, REGISTER_OBJECT, REGISTER_FROM_TO, REGISTER_DESC, REGISTER_NUMBER, REGISTER_FILE = range(7)

ADMIN_IDS = [7363233852]  # Замініть на свій Telegram ID
DOCS_DIR_IN = "incoming_docs"
DOCS_DIR_OUT = "outgoing_docs"
CHANNEL_CHAT_ID = -1002603457925  # chat_id вашого каналу

os.makedirs(DOCS_DIR_IN, exist_ok=True)
os.makedirs(DOCS_DIR_OUT, exist_ok=True)

# --- SQLite: init ---
def init_db():
    conn = sqlite3.connect("letters.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            date TEXT NOT NULL,
            number TEXT NOT NULL,
            object TEXT,
            from_to TEXT,
            description TEXT,
            filename TEXT,
            status TEXT DEFAULT 'new',
            file_url TEXT
        );
    """)
    conn.commit()
    conn.close()

# --- DB functions ---
def insert_letter(letter_type, date, number, object_name, from_to, description, filename, status="new", file_url=""):
    conn = sqlite3.connect("letters.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO letters (type, date, number, object, from_to, description, filename, status, file_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (letter_type, date, number, object_name, from_to, description, filename, status, file_url))
    conn.commit()
    conn.close()

def find_letter_by_number(number):
    conn = sqlite3.connect("letters.db")
    cursor = conn.cursor()
    cursor.execute("SELECT type, date, number, object, from_to, description, status, file_url FROM letters WHERE number = ?", (number,))
    row = cursor.fetchone()
    conn.close()
    return row

# --- register_file handler ---
async def register_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document
    journal = context.user_data['journal']
    now = datetime.datetime.now().strftime("%Y-%m-%d")
    number = context.user_data['number']

    filename = f"{number.replace('/', '_')}_{file.file_name}"
    path = os.path.join(DOCS_DIR_IN if journal == 'in' else DOCS_DIR_OUT, filename)
    await file.get_file().download_to_drive(path)

    caption = f"{number} ({now})\n{context.user_data['object']}\n{context.user_data['desc']}"
    with open(path, "rb") as f:
        sent = await context.bot.send_document(chat_id=CHANNEL_CHAT_ID, document=f, caption=caption)

    file_url = f"https://t.me/c/{str(CHANNEL_CHAT_ID)[4:]}/{sent.message_id}"

    insert_letter(
        letter_type=journal,
        date=now,
        number=number,
        object_name=context.user_data['object'],
        from_to=context.user_data['from_to'],
        description=context.user_data['desc'],
        filename=filename,
        file_url=file_url
    )

    await update.message.reply_text(f"✅ Зареєстровано / Registered\nНомер: {number}\nДата: {now}")
    return ConversationHandler.END

# --- пошук з кнопкою ---
async def show_found_letter(update, context, number):
    letter = find_letter_by_number(number)
    if not letter:
        await update.message.reply_text("❌ Лист не знайдено")
        return ConversationHandler.END
    t, date, number, obj, who, desc, status, url = letter
    msg = f"📄 *{number}*\nДата: {date}\nТип: {'Вхідний' if t == 'in' else 'Вихідний'}\nОбʼєкт: {obj}\nВід/Кому: {who}\nОпис: {desc}\nСтатус: {status}"
    keyboard = [
        [InlineKeyboardButton("📂 Відкрити документ", url=url)] if url else [],
        [InlineKeyboardButton("✅ Опрацьовано", callback_data=f"mark_{number}"),
         InlineKeyboardButton("🗑 Видалити", callback_data=f"delete_{number}")],
        [InlineKeyboardButton("🏠 На головну", callback_data='menu')]
    ]
    keyboard = [row for row in keyboard if row]  # remove empty
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END
