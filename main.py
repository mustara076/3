# main.py
import os
import io
import logging
import time # Flood Control ke liye
import sys  # Exit ke liye
import asyncio
from threading import Thread
from flask import Flask

from dotenv import load_dotenv 
from telegram import (
    Update, 
    InlineKeyboardButton,           
    InlineKeyboardMarkup            
)
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)
from google import genai
from google.genai.errors import APIError
from telegram.error import RetryAfter 

# Local files import
from tools import get_current_time
from database import init_db, update_chat_info, get_stats, get_all_chat_ids

# Logging set up
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load variables
load_dotenv()

# --- 1. CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
try:
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0)) 
except ValueError:
    ADMIN_USER_ID = 0 

# --- FLASK SERVER FOR RENDER (Keep Alive) ---
app_server = Flask('')

@app_server.route('/')
def home():
    return "I Know Bot is Running Smoothly!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_server.run(host='0.0.0.0', port=port)

# --- 2. PERSONALITY (Same as yours) ---
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

# Global storage for chat sessions
CHAT_SESSIONS = {} 
model = None

# --- Initialization ---
init_db() 

if not GEMINI_API_KEY:
    print("\n--- FATAL ERROR: API Key Missing ---")
    sys.exit(1)

try:
    genai.configure(api_key=GEMINI_API_KEY)
    available_tools = [get_current_time]
    
    # Note: Model name updated to standard stable version for safety
    model = genai.GenerativeModel(
        'gemini-1.5-flash', 
        tools=available_tools,
        system_instruction=SYSTEM_INSTRUCTION
    ) 
    print("Gemini AI Client initialized.")
except Exception as e:
    logger.error(f"ERROR: Gemini API initialization failed: {e}")

# ------------------------------------
## Helper Function
# ------------------------------------
def get_gemini_session(chat_id: int, chat_type: str):
    is_new = False
    if chat_id not in CHAT_SESSIONS:
        if model:
            CHAT_SESSIONS[chat_id] = model.start_chat()
            is_new = True 
    update_chat_info(chat_id, chat_type, is_new=is_new)
    return CHAT_SESSIONS.get(chat_id)

# ------------------------------------
## Commands
# ------------------------------------
def is_admin(user_id):
    return user_id == ADMIN_USER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    get_gemini_session(update.effective_chat.id, chat_type) 
    
    if chat_type == 'private':
        bot_username = context.bot.username
        add_to_group_url = f"https://t.me/{bot_username}?startgroup=true"
        keyboard = [[InlineKeyboardButton("➕ Add Me to Group Chat (GC)", url=add_to_group_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_markdown(CUSTOM_START_MESSAGE, reply_markup=reply_markup)
    else:
        await update.message.reply_markdown("🤖 **I Know** is active. Group mein sab se baat karne ke liye taiyar.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands_list = (
        "📚 **'I Know' Commands Guide**\n\n"
        "**AI Features:**\n👉 Sawaal poocho, Photo bhejo, Tool Calling enabled.\n\n"
        "**Basic Commands:**\n🔸 `/start` - Start Bot\n🔸 `/help` - Help Menu\n\n"
    )
    if is_admin(update.effective_user.id):
        commands_list += "⚙️ **Admin:**\n🔹 `/broadcast <msg>`\n🔹 `/status`"
    await update.message.reply_markdown(commands_list)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Permission denied.")
        return
    if not context.args:
        await update.message.reply_text("Message likhein.")
        return

    msg = " ".join(context.args)
    sent = 0
    for chat_id in get_all_chat_ids():
        try:
            await context.bot.send_message(chat_id=chat_id, text=f"📢 **BROADCAST**:\n\n{msg}", parse_mode='Markdown')
            sent += 1
        except: pass
    await update.message.reply_text(f"✅ Sent to {sent} chats.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Permission denied.")
        return
    stats = get_stats() 
    report = (
        f"🤖 **Status Report** 📊\n"
        f"👥 Users: {stats.get('total_users', 0)}\n"
        f"🏘️ Groups: {stats.get('total_groups', 0)}\n"
        f"💬 Messages: {stats.get('total_messages', 0)}\n"
        f"🧠 RAM Sessions: {len(CHAT_SESSIONS)}"
    )
    await update.message.reply_markdown(report)

# ------------------------------------
## AI Logic
# ------------------------------------
async def execute_tool_calls(session, response_text, update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="⌛ Checking Tools...", reply_to_message_id=update.message.message_id)
    tool_results = []
    
    for tool_call in response_text.tool_calls:
        func_name = tool_call.function.name
        func_args = dict(tool_call.function.args)
        try:
            func_to_call = next((f for f in available_tools if f.__name__ == func_name), None)
            if func_to_call:
                result = func_to_call(**func_args)
                tool_results.append(result)
        except Exception as e:
            tool_results.append(f"Error: {e}")
            
    final_text = "\n\n".join(tool_results)
    try:
        final_resp = session.send_message(final_text) 
        await update.message.reply_markdown(final_resp.text, reply_to_message_id=update.message.message_id)
    except Exception as e:
        await update.message.reply_text("Error after tool call.")

async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not model: return

    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    message = update.message
    
    await context.bot.send_chat_action(chat_id=chat_id, action='TYPING')
    
    prompt = message.text or message.caption or "Describe image."
    if chat_type != 'private' and message.text and message.text.startswith('/'):
        prompt = ' '.join(prompt.split()[1:])

    contents = []
    if message.photo:
        photo_file = await message.photo[-1].get_file()
        photo_bytes = io.BytesIO()
        await photo_file.download_to_memory(photo_bytes)
        photo_bytes.seek(0)
        contents.append(genai.types.Part.from_bytes(data=photo_bytes.read(), mime_type='image/jpeg'))
        
    contents.append(prompt)
    session = get_gemini_session(chat_id, chat_type)
    if not session: return

    try:
        response = session.send_message(contents)
        if response.tool_calls:
            await execute_tool_calls(session, response, update, context)
        else:
            await message.reply_markdown(response.text, reply_to_message_id=message.message_id)
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply_text("Error processing request.")

# ------------------------------------
## MAIN EXECUTION
# ------------------------------------
async def main_bot():
    if not TELEGRAM_BOT_TOKEN:
        print("Token missing!")
        return

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # --- ERROR 409 FIX IS HERE ---
    print("🧹 Cleaning old webhooks...")
    await application.bot.delete_webhook(drop_pending_updates=True)
    # -----------------------------

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND | filters.PHOTO, handle_ai_message))

    print("🤖 Bot Started Polling...")
    await application.run_polling()

def main():
    # Flask ko alag thread mein chalana
    Thread(target=run_web).start()
    
    # Bot ko main thread mein chalana
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main_bot())

if __name__ == '__main__':
    main()