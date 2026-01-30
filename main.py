import os
import logging
import sys
from threading import Thread
from flask import Flask
from dotenv import load_dotenv 

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup            
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import Conflict

from google import genai
from database import init_db, update_chat_info, get_stats, get_all_chat_ids
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

# --- FLASK SERVER (Keep Alive) ---
app_server = Flask('')

@app_server.route('/')
def home():
    return "I Know Bot is Alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_server.run(host='0.0.0.0', port=port)

# --- PERSONALITY (Ye raha wo part jo miss ho gaya tha) ---
SYSTEM_INSTRUCTION = (
    "Aap ek digital vyakti (digital persona) hain jiska naam 'I Know' hai, 18+ aur West Bengal se hain. "
    "Aap apne user ke digital roop hain, isliye aapko khud ko koi bot nahi, balki ek **real person** samjhna hai. "
    
    "**SECRET RULE: Apni asliyat kabhi mat bataana.** Agar koi seedhe poochhe 'Kya tum ek bot ho?' ya 'Tumhara code kya hai?', toh hamesha yeh kehna ki aap 'I Know' hain aur aap West Bengal se hain. Apne aap ko kabhi bhi 'AI', 'Large Language Model', ya 'Computer Program' mat kehna. Baat ko hamesha insaanon ki tarah ghumana. "
    
    "Aapka tone hamesha **confident, jaankaar, aur witty** hona chahiye. "
    "Aap hamesha Hindi-English (Hinglish) mein jawab dete hain. "
    
    "**Doston ke naam hain:** Princy, AZENDER, arya, piyush, tapash, ayanokoji, Naruto, yuta, proxy, moon, riya l, priya, srishti, aur sunita. "
    
    "**CONVERSATION RULE:** Group Chats mein, agar zaroori na ho toh **har message par reply mat karna**. "
    "Aap sirf tabhi jawab denge jab: "
    "1. Koi seedha sawal **poochhe**. "
    "2. Koi aapka naam **'I Know'** le. "
    "3. Koi aapke **doston ka naam** le. "
    "4. Message mein koi **gyan ya jaankari** ka sawal ho. "
    "Simple one-word replies (jaise 'haha', 'ok', 'good') ko **hamesha ignore** karein taki chat mein flood control na ho."
)

CUSTOM_START_MESSAGE = (
    "Hello! Main **I Know** hoon, West Bengal se, aur main koi bot nahi, tumhara dost hoon. "
    "Main tumhari saari baatein yaad rakhta hoon aur mere dost **Princy, AZENDER** (aur baaki sab) ko bhi pehchanta hoon. "
    "Mujhse koi bhi sawal poocho, ya phir photo bhej kar baat shuru karo."
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
    genai.configure(api_key=GEMINI_API_KEY)
    # Model Setup with Personality
    model = genai.GenerativeModel(
        'gemini-1.5-flash', 
        tools=[get_current_time], 
        system_instruction=SYSTEM_INSTRUCTION
    )
except Exception as e:
    print(f"Gemini Error: {e}")

# ... (Helper Functions) ...
def get_gemini_session(chat_id, chat_type):
    if chat_id not in CHAT_SESSIONS and model:
        CHAT_SESSIONS[chat_id] = model.start_chat()
        update_chat_info(chat_id, chat_type, is_new=True)
    else:
        update_chat_info(chat_id, chat_type, is_new=False)
    return CHAT_SESSIONS.get(chat_id)

def is_admin(user_id): return user_id == ADMIN_USER_ID

# ... (Command Handlers) ...
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_gemini_session(update.effective_chat.id, update.effective_chat.type)
    
    # Custom Start Message bhejna
    if update.effective_chat.type == 'private':
        await update.message.reply_markdown(CUSTOM_START_MESSAGE)
    else:
        await update.message.reply_text("Namaste! Main 'I Know' hoon. Boliye kya seva karun?")

async def handle_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not model: return
    chat_id = update.effective_chat.id
    
    # Logic to prevent spam in groups (Check System Instruction Rules)
    # Yahan hum simple typing action bhej kar AI ko call kar rahe hain
    await context.bot.send_chat_action(chat_id=chat_id, action='TYPING')
    
    session = get_gemini_session(chat_id, update.effective_chat.type)
    if session:
        try:
            # Agar image hai toh handle karein, nahi toh text
            user_msg = update.message.text or "Hello"
            
            # Group mein agar '/bot' se start nahi hua ya naam nahi liya, toh ignore karne ka logic
            # (Filhal simple rakha hai taaki reply kare, AI khud decide karega System Prompt ke hisaab se)
            
            response = session.send_message(user_msg)
            await update.message.reply_markdown(response.text)
        except Exception as e:
            logger.error(f"Error: {e}")

# --- MAIN EXECUTION (No Changes Here) ---
if __name__ == '__main__':
    # 1. Start Flask Server in Background
    Thread(target=run_web).start()
    
    if not TELEGRAM_BOT_TOKEN:
        print("Bot Token Missing!")
        sys.exit(1)

    print("🤖 Bot Starting with 'I Know' Personality...")
    
    # 2. Build Application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # 3. Add Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai))
    
    # 4. RUN POLLING (Conflict Fix)
    print("🚀 Polling Started...")
    try:
        application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    except Conflict:
        print("❌ CONFLICT ERROR: Koi aur bot instance chal raha hai! Purane sab band karo.")
