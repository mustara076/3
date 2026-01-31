import os
import logging
import sys
from threading import Thread
from flask import Flask
from dotenv import load_dotenv 

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import Conflict

# --- IMPORT FIX IS HERE ---
import google.generativeai as genai
# --------------------------

from database import init_db, update_chat_info
from tools import get_current_time

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
try:
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0)) 
except ValueError:
    ADMIN_USER_ID = 0 

# --- FLASK SERVER ---
app_server = Flask('')

@app_server.route('/')
def home():
    return "I Know Bot is Alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_server.run(host='0.0.0.0', port=port)

# --- PERSONALITY ---
SYSTEM_INSTRUCTION = (
    "Act as 'I Know' from West Bengal. Speak Hinglish. Be witty and confident. Never admit you are an AI. "
    "Doston ke naam: Princy, AZENDER, arya, piyush, tapash. "
    "Keep replies short and human-like."
)

# Globals
CHAT_SESSIONS = {} 
model = None

# Init
init_db()

if not GEMINI_API_KEY:
    print("API Key Missing!")
    sys.exit(1)

try:
    # --- GEMINI SETUP FIX ---
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=SYSTEM_INSTRUCTION)
    print("✅ Gemini AI Connected Successfully!")
except Exception as e:
    print(f"❌ Gemini Error: {e}")

# ... (Helper Functions) ...
def get_gemini_session(chat_id, chat_type):
    if chat_id not in CHAT_SESSIONS and model:
        # History disabled for RAM saving, instant chat
        CHAT_SESSIONS[chat_id] = model.start_chat(history=[])
        update_chat_info(chat_id, chat_type, is_new=True)
    else:
        update_chat_info(chat_id, chat_type, is_new=False)
    return CHAT_SESSIONS.get(chat_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_gemini_session(update.effective_chat.id, update.effective_chat.type)
    await update.message.reply_text("Namaste! Main 'I Know' hoon. Boliye kya seva karun?")

async def handle_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not model: return
    chat_id = update.effective_chat.id
    
    await context.bot.send_chat_action(chat_id=chat_id, action='TYPING')
    
    session = get_gemini_session(chat_id, update.effective_chat.type)
    if session:
        try:
            user_msg = update.message.text or "Hello"
            response = session.send_message(user_msg)
            await update.message.reply_text(response.text)
        except Exception as e:
            logger.error(f"Error: {e}")
            # Agar error aaye, toh session reset karo
            if chat_id in CHAT_SESSIONS: del CHAT_SESSIONS[chat_id]

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    Thread(target=run_web).start()
    
    if not TELEGRAM_BOT_TOKEN:
        print("Bot Token Missing!")
        sys.exit(1)

    print("🤖 Bot Starting...")
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai))
    
    print("🚀 Polling Started...")
    try:
        application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    except Conflict:
        print("❌ CONFLICT ERROR: Koi aur bot chal raha hai!")
