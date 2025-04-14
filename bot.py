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

# --- Telegram Handlers ---
async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"🆔 Chat ID: {chat_id}")

# --- Init ---
init_db()

app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

app.add_handler(CommandHandler("get_chat_id", get_chat_id))

if __name__ == '__main__':
    app.run_polling()
