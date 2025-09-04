# bot.py
import logging
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters

from config import BOT_TOKEN
from handlers import *
from access_control import restricted_access

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Основная функция запуска бота"""
    if not BOT_TOKEN:
        logger.error("Не задан BOT_TOKEN. Задайте его в config.py или через переменную окружения.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_router))
    application.add_handler(CommandHandler("update", update_statuses))

    # Conversation handler для выдачи
    issue_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('issue', start_issue)],
        states={
            MAC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mac)],
            ROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_room)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_contact)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    application.add_handler(issue_conv_handler)

    # Conversation handler для возврата
    return_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('return', start_return)],
        states={
            MAC: [MessageHandler(filters.TEXT & ~filters.COMMAND, return_get_identifier)],
            CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    application.add_handler(return_conv_handler)

    # Conversation handler для продления
    extend_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('extend', start_extend)],
        states={
            MAC: [MessageHandler(filters.TEXT & ~filters.COMMAND, extend_get_identifier)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, extend_get_date)],
            CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    application.add_handler(extend_conv_handler)

    # Conversation handler для добавления комментария
    comment_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add_comment', start_add_comment)],
        states={
            MAC: [MessageHandler(filters.TEXT & ~filters.COMMAND, comment_get_identifier)],
            COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_comment)],
            CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    application.add_handler(comment_conv_handler)

    # Conversation handler для изменения владельца
    owner_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('change_owner', start_change_owner)],
        states={
            MAC: [MessageHandler(filters.TEXT & ~filters.COMMAND, owner_get_identifier)],
            NEW_OWNER: [MessageHandler(filters.TEXT & ~filters.COMMAND, owner_get_name)],
            NEW_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, owner_get_contact)],
            CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    application.add_handler(owner_conv_handler)

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()