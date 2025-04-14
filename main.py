import os
import datetime
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler,
    filters, CallbackQueryHandler, ConversationHandler
)

LANGUAGE, JOURNAL, REGISTER_OBJECT, REGISTER_FROM_TO, REGISTER_DESC, REGISTER_NUMBER, REGISTER_FILE = range(7)

ADMIN_IDS = [7363233852]
DOCS_DIR_IN = "incoming_docs"
DOCS_DIR_OUT = "outgoing_docs"
CHANNEL_CHAT_ID = -1002603457925

os.makedirs(DOCS_DIR_IN, exist_ok=True)
os.makedirs(DOCS_DIR_OUT, exist_ok=True)

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

def update_status(number, new_status):
    conn = sqlite3.connect("letters.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE letters SET status = ? WHERE number = ?", (new_status, number))
    conn.commit()
    conn.close()

def delete_letter(number):
    conn = sqlite3.connect("letters.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM letters WHERE number = ?", (number,))
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Українська 🇺🇦", callback_data='ua'),
                 InlineKeyboardButton("English 🇬🇧", callback_data='en')]]
    await update.message.reply_text("Choose language / Оберіть мову:", reply_markup=InlineKeyboardMarkup(keyboard))
    return LANGUAGE

async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.callback_query.data
    context.user_data['lang'] = lang
    await update.callback_query.answer()
    keyboard = [[InlineKeyboardButton("📥 Вхідний / Incoming", callback_data='in'),
                 InlineKeyboardButton("📤 Вихідний / Outgoing", callback_data='out')]]
    await update.callback_query.edit_message_text("Оберіть журнал / Choose journal:", reply_markup=InlineKeyboardMarkup(keyboard))
    return JOURNAL

async def choose_journal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['journal'] = update.callback_query.data
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Введіть назву обʼєкта / Enter object name:")
    return REGISTER_OBJECT

async def manual_object(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['object'] = update.message.text
    return await ask_from_to(update, context)

async def ask_from_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    journal = context.user_data['journal']
    if journal == 'in':
        await update.message.reply_text("Від кого лист? / From whom?")
    else:
        await update.message.reply_text("Кому адресовано лист? / To whom?")
    return REGISTER_FROM_TO

async def register_from_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['from_to'] = update.message.text
    await update.message.reply_text("Короткий опис / Short description:")
    return REGISTER_DESC

async def register_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['desc'] = update.message.text
    now = datetime.datetime.now()
    context.user_data['number'] = f"{now.timestamp():.0f}"[-4:] + f"/{now.year % 100}"
    await update.message.reply_text(f"Ваш номер: {context.user_data['number']}\nПрикріпіть файл / Attach the document:")
    return REGISTER_FILE

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

    await update.message.reply_text(f"✅ Зареєстровано\nНомер: {number}\nДата: {now}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Скасовано / Cancelled")
    return ConversationHandler.END

# === INIT APP ===
init_db()
app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        LANGUAGE: [CallbackQueryHandler(choose_language)],
        JOURNAL: [CallbackQueryHandler(choose_journal)],
        REGISTER_OBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_object)],
        REGISTER_FROM_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_from_to)],
        REGISTER_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_desc)],
        REGISTER_FILE: [MessageHandler(filters.Document.ALL, register_file)],
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)

app.add_handler(conv_handler)

if __name__ == '__main__':
    app.run_polling()
