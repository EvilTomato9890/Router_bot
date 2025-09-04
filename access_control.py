# access_control.py
from telegram import Update
from telegram.ext import ContextTypes

from config import ALLOWED_USER_IDS

async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет, имеет ли пользователь доступ к боту"""
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        return False
    return True

def restricted_access(func):
    """Декоратор для ограничения доступа к командам"""
    async def wrapped(update, context, *args, **kwargs):
        if not await check_access(update, context):
            return
        return await func(update, context, *args, **kwargs)
    return wrapped