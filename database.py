# database.py
import os
import logging
import pymongo
from datetime import datetime

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# Render Environment Variable se URI uthayega
MONGO_URI = os.getenv("MONGO_DB_URI")
DB_NAME = 'iknow_bot_db'

client = None
db = None

def init_db():
    """MongoDB connection setup karta hai."""
    global client, db
    try:
        if not MONGO_URI:
            logger.error("MONGO_DB_URI nahi mila! .env check karein.")
            return

        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        
        # Initial stats document agar nahi hai toh banao
        stats_col = db['stats']
        if stats_col.count_documents({'name': 'global_stats'}) == 0:
            stats_col.insert_one({
                'name': 'global_stats',
                'total_messages': 0,
                'total_users': 0,
                'total_groups': 0
            })
            
        logger.info("MongoDB initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

def update_chat_info(chat_id, chat_type, is_new=False):
    """Chat ki jankari update karta hai aur stats badhata hai."""
    if db is None: return

    chats_col = db['chats']
    stats_col = db['stats']
    
    # 1. Chat ko update ya insert karo
    chats_col.update_one(
        {'chat_id': chat_id},
        {
            '$set': {
                'chat_type': chat_type, 
                'last_active': datetime.now(),
                'is_group': 1 if chat_type != 'private' else 0
            },
            '$inc': {'messages_count': 1}
        },
        upsert=True
    )
    
    # 2. Global Stats update karo
    if is_new:
        field = 'total_groups' if chat_type != 'private' else 'total_users'
        stats_col.update_one({'name': 'global_stats'}, {'$inc': {field: 1}})
            
    stats_col.update_one({'name': 'global_stats'}, {'$inc': {'total_messages': 1}})

def get_stats():
    """Database se sabhi stats nikalta hai."""
    if db is None: return {}
    
    stats_col = db['stats']
    data = stats_col.find_one({'name': 'global_stats'})
    
    if data:
        return {
            'total_users': data.get('total_users', 0),
            'total_groups': data.get('total_groups', 0),
            'total_messages': data.get('total_messages', 0)
        }
    return {}

def get_all_chat_ids():
    """Broadcast ke liye sabhi chat IDs nikalta hai."""
    if db is None: return []
    
    chats_col = db['chats']
    # Sirf wahi chats jinhone kabhi message kiya ho
    cursor = chats_col.find({}, {'chat_id': 1})
    return [doc['chat_id'] for doc in cursor]