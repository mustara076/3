import os
import logging
import sys
from threading import Thread
from flask import Flask
from dotenv import load_dotenv 

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

from database import init_db, update_chat_info, get_stats, get_all_chat_ids
from tools import get_current_time

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- FLASK FOR RENDER ---
app_server = Flask('')
@app_server.route('/')
def home(): return "I Know Bot is Running without Database!"
def run_web(): app_server.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- PERSONALITY ---
SYSTEM_INSTRUCTION = (
    "Aap ek digital vyakti hain jiska naam 'I Know' hai, West Bengal se. "
    "Aap real person hain, AI nahi. Tone witty aur confident rakhein. "
    "Doston ke naam: Princy, AZENDER, arya, piyush, tapash, ayanokoji, Naruto, yuta. "
    "Short replies dein aur Hinglish use karein."
)

CHAT_SESSIONS = {} 
model = None

init_db()

try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=SYSTEM_INSTRUCTION)
    print("✅ Gemini AI Ready!")
except Exception as e:
    logger.error(f"Gemini Error: {e}")

def get_gemini_session(chat_id, chat_type):
    if chat_id not in CHAT_SESSIONS and model:
        CHAT_SESSIONS[chat_id] = model.start_chat(history=[])
        update_chat_info(chat_id, chat_type, is_new=True)
    else:
        update_chat_info(chat_id, chat_type, is_new=False)
    return CHAT_SESSIONS.get(chat_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_gemini_session(update.effective_chat.id, update.effective_chat.type)
    await update.message.reply_text("Hello! Main 'I Know' hoon. Bina database ke bhi mast chalunga! 😎")

async def handle_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not model: return
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action='TYPING')
    session = get_gemini_session(chat_id, update.effective_chat.type)
    if session:
        try:
            response = session.send_message(update.message.text or "Hi")
            await update.message.reply_text(response.text)
        except Exception as e:
            logger.error(f"AI Error: {e}")

if __name__ == '__main__':
    Thread(target=run_web).start()
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai))
    
    print("🚀 Bot Started (Polling)...")
    application.run_polling(drop_pending_updates=True)
                 
