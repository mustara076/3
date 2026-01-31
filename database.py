# database.py
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Ye data RAM mein rahega (Restart par reset ho jayega)
temp_stats = {
    'total_messages': 0,
    'total_users': 0,
    'total_groups': 0
}
temp_chats = set()

def init_db():
    logger.info("RAM-based storage initialized (No MongoDB).")

def update_chat_info(chat_id, chat_type, is_new=False):
    """Stats ko RAM mein update karta hai."""
    temp_stats['total_messages'] += 1
    
    if chat_id not in temp_chats:
        temp_chats.add(chat_id)
        if chat_type == 'private':
            temp_stats['total_users'] += 1
        else:
            temp_stats['total_groups'] += 1

def get_stats():
    """RAM se stats nikalta hai."""
    return temp_stats

def get_all_chat_ids():
    """Broadcast ke liye list (Note: Restart ke baad ye khali ho jayegi)."""
    return list(temp_chats)
    
