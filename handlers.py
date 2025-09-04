# handlers.py
import logging
import re
from datetime import datetime, timedelta

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

from config import DEFAULT_ISSUE_PERIOD
from sheets import sheets_helper
from access_control import restricted_access

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler'а
MAC, ROOM, NAME, CONTACT, DATE, CONFIRMATION, COMMENT, NEW_OWNER, NEW_CONTACT = range(9)

def parse_date(date_str):
    """Парсит строку даты в формате +Nd или YYYY-MM-DD"""
    if date_str.startswith('+'):
        try:
            days = int(date_str[1:])
            return datetime.now() + timedelta(days=days)
        except ValueError:
            return None
    else:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return None

@restricted_access
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}!\n"
        "Я бот для учета роутеров в общежитии.\n"
        "Доступные команды:\n"
        "/add <MAC> - Добавить роутер\n"
        "/issue - Выдать роутер\n"
        "/return - Принять роутер\n"
        "/extend - Продлить срок\n"
        "/update - Проверить просрочки\n"
        "/add_comment - Добавить комментарий\n"
        "/change_owner - Изменить владельца"
    )

@restricted_access
async def add_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /add"""
    if not context.args:
        await update.message.reply_text("Использование: /add <MAC-адрес>")
        return

    mac_address = ' '.join(context.args)
    if not re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", mac_address):
        await update.message.reply_text("Неверный формат MAC-адреса.")
        return

    row_num, _ = sheets_helper.find_row_by_mac(mac_address)
    if row_num:
        await update.message.reply_text("Этот MAC-адрес уже есть в таблице.")
        return

    try:
        all_values = sheets_helper.sheet.get_all_values()
        next_row = len(all_values) + 1
        sheets_helper.update_cell(next_row, 2, mac_address)  # Колонка B (MAC)
        sheets_helper.update_cell(next_row, 4, "Свободен")   # Колонка D (Status)
        await update.message.reply_text(f"Роутер с MAC {mac_address} успешно добавлен.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении роутера: {e}")
        await update.message.reply_text("Произошла ошибка при добавлении.")

@restricted_access
async def start_issue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс выдачи роутера"""
    await update.message.reply_text(
        "Введите MAC-адрес роутера:",
        reply_markup=ReplyKeyboardRemove()
    )
    return MAC

@restricted_access
async def get_mac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает MAC-адрес от пользователя"""
    mac_address = update.message.text
    if not re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", mac_address):
        await update.message.reply_text("Неверный формат MAC. Попробуйте еще раз или /cancel.")
        return MAC

    row_num, row_data = sheets_helper.find_row_by_mac(mac_address)
    if not row_num:
        await update.message.reply_text("Роутер с таким MAC-адресом не найден.")
        return MAC

    current_status = row_data[3] if len(row_data) > 3 else ""
    if current_status != "Свободен":
        await update.message.reply_text("Этот роутер сейчас не свободен.")
        return ConversationHandler.END

    context.user_data['issue_mac'] = mac_address
    context.user_data['issue_row'] = row_num

    await update.message.reply_text("Введите номер комнаты:")
    return ROOM

@restricted_access
async def get_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает номер комнаты"""
    room = update.message.text
    context.user_data['issue_room'] = room
    await update.message.reply_text("Введите ФИО получателя:")
    return NAME

@restricted_access
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает ФИО"""
    name = update.message.text
    context.user_data['issue_name'] = name
    await update.message.reply_text("Введите контакты (Telegram или телефон):")
    return CONTACT

@restricted_access
async def get_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает контакты"""
    contact = update.message.text
    context.user_data['issue_contact'] = contact
    await update.message.reply_text("Введите срок выдачи (+Nd или YYYY-MM-DD):")
    return DATE

@restricted_access
async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает дату и завершает процесс выдачи"""
    date_str = update.message.text
    return_date = parse_date(date_str)

    if not return_date:
        await update.message.reply_text("Неверный формат даты. Используйте +Nd или YYYY-MM-DD.")
        return DATE

    return_date_str = return_date.strftime("%Y-%m-%d")
    user_data = context.user_data
    row_num = user_data['issue_row']
    room = user_data['issue_room']
    name = user_data['issue_name']
    contact = user_data['issue_contact']
    
    issue_date_str = datetime.now().strftime("%Y-%m-%d")

    # Показываем информацию для подтверждения
    info_text = (
        f"Подтвердите выдачу роутера:\n\n"
        f"MAC: {user_data['issue_mac']}\n"
        f"Комната: {room}\n"
        f"Владелец: {name}\n"
        f"Контакты: {contact}\n"
        f"Дата выдачи: {issue_date_str}\n"
        f"Вернуть до: {return_date_str}\n\n"
        f"Подтверждаете? (да/нет)"
    )
    
    context.user_data['pending_operation'] = 'issue'
    context.user_data['pending_data'] = {
        'row_num': row_num,
        'room': room,
        'name': name,
        'contact': contact,
        'issue_date': issue_date_str,
        'return_date': return_date_str
    }
    
    await update.message.reply_text(info_text)
    return CONFIRMATION

@restricted_access
async def start_return(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс возврата роутера"""
    await update.message.reply_text("Введите номер комнаты или MAC-адрес роутера для возврата:")
    return MAC

@restricted_access
async def return_get_identifier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает идентификатор для возврата"""
    identifier = update.message.text
    
    # Определяем, это MAC или номер комнаты
    if re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", identifier):
        row_num, row_data = sheets_helper.find_row_by_mac(identifier)
    else:
        row_num, row_data = sheets_helper.find_row_by_room(identifier)

    if not row_num:
        await update.message.reply_text("Роутер не найден. Попробуйте еще раз или /cancel.")
        return MAC

    # Показываем информацию о роутере
    info_text = sheets_helper.get_router_info(row_data)
    info_text += "\n\nВы уверены, что хотите принять этот роутер? (да/нет)"
    
    context.user_data['pending_operation'] = 'return'
    context.user_data['pending_row_num'] = row_num
    
    await update.message.reply_text(info_text)
    return CONFIRMATION

@restricted_access
async def start_extend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс продления срока"""
    await update.message.reply_text("Введите номер комнаты или MAC-адрес роутера для продления:")
    return MAC

@restricted_access
async def extend_get_identifier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает идентификатор для продления"""
    identifier = update.message.text
    
    # Определяем, это MAC или номер комнаты
    if re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", identifier):
        row_num, row_data = sheets_helper.find_row_by_mac(identifier)
    else:
        row_num, row_data = sheets_helper.find_row_by_room(identifier)

    if not row_num:
        await update.message.reply_text("Роутер не найден. Попробуйте еще раз или /cancel.")
        return MAC

    context.user_data['pending_operation'] = 'extend'
    context.user_data['pending_row_num'] = row_num
    
    await update.message.reply_text("Введите новый срок (+Nd или YYYY-MM-DD):")
    return DATE

@restricted_access
async def extend_get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает дату для продления"""
    date_str = update.message.text
    return_date = parse_date(date_str)

    if not return_date:
        await update.message.reply_text("Неверный формат даты. Используйте +Nd или YYYY-MM-DD.")
        return DATE

    return_date_str = return_date.strftime("%Y-%m-%d")
    row_num = context.user_data['pending_row_num']
    
    # Получаем текущие данные для подтверждения
    _, row_data = sheets_helper.find_row_by_mac(sheets_helper.sheet.cell(row_num, 2).value)
    info_text = sheets_helper.get_router_info(row_data)
    info_text += f"\n\nНовый срок возврата: {return_date_str}\n\nПодтверждаете продление? (да/нет)"
    
    context.user_data['pending_data'] = {'return_date': return_date_str}
    
    await update.message.reply_text(info_text)
    return CONFIRMATION

@restricted_access
async def start_add_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс добавления комментария"""
    await update.message.reply_text("Введите номер комнаты или MAC-адрес роутера для добавления комментария:")
    return MAC

@restricted_access
async def comment_get_identifier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает идентификатор для добавления комментария"""
    identifier = update.message.text
    
    # Определяем, это MAC или номер комнаты
    if re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", identifier):
        row_num, row_data = sheets_helper.find_row_by_mac(identifier)
    else:
        row_num, row_data = sheets_helper.find_row_by_room(identifier)

    if not row_num:
        await update.message.reply_text("Роутер не найден. Попробуйте еще раз или /cancel.")
        return MAC

    context.user_data['pending_operation'] = 'add_comment'
    context.user_data['pending_row_num'] = row_num
    
    await update.message.reply_text("Введите комментарий:")
    return COMMENT

@restricted_access
async def get_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает комментарий"""
    comment = update.message.text
    context.user_data['pending_comment'] = comment
    
    row_num = context.user_data['pending_row_num']
    _, row_data = sheets_helper.find_row_by_mac(sheets_helper.sheet.cell(row_num, 2).value)
    info_text = sheets_helper.get_router_info(row_data)
    info_text += f"\n\nНовый комментарий: {comment}\n\nПодтверждаете добавление? (да/нет)"
    
    await update.message.reply_text(info_text)
    return CONFIRMATION

@restricted_access
async def start_change_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс изменения владельца"""
    await update.message.reply_text("Введите номер комнаты или MAC-адрес роутера для изменения владельца:")
    return MAC

@restricted_access
async def owner_get_identifier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает идентификатор для изменения владельца"""
    identifier = update.message.text
    
    # Определяем, это MAC или номер комнаты
    if re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", identifier):
        row_num, row_data = sheets_helper.find_row_by_mac(identifier)
    else:
        row_num, row_data = sheets_helper.find_row_by_room(identifier)

    if not row_num:
        await update.message.reply_text("Роутер не найден. Попробуйте еще раз или /cancel.")
        return MAC

    context.user_data['pending_operation'] = 'change_owner'
    context.user_data['pending_row_num'] = row_num
    
    await update.message.reply_text("Введите ФИО нового владельца:")
    return NEW_OWNER

@restricted_access
async def owner_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает имя нового владельца"""
    name = update.message.text
    context.user_data['pending_new_owner'] = name
    
    await update.message.reply_text("Введите контакты нового владельца:")
    return NEW_CONTACT

@restricted_access
async def owner_get_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает контакты нового владельца"""
    contact = update.message.text
    row_num = context.user_data['pending_row_num']
    
    # Получаем текущие данные для подтверждения
    _, row_data = sheets_helper.find_row_by_mac(sheets_helper.sheet.cell(row_num, 2).value)
    info_text = sheets_helper.get_router_info(row_data)
    info_text += f"\n\nНовый владелец: {context.user_data['pending_new_owner']}\n"
    info_text += f"Новые контакты: {contact}\n\n"
    info_text += "Подтверждаете изменение? (да/нет)"
    
    context.user_data['pending_data'] = {
        'name': context.user_data['pending_new_owner'],
        'contact': contact
    }
    
    await update.message.reply_text(info_text)
    return CONFIRMATION

@restricted_access
async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает подтверждение действий"""
    text = update.message.text.lower()
    
    if text not in ['да', 'нет']:
        await update.message.reply_text("Пожалуйста, ответьте 'да' или 'нет'.")
        return CONFIRMATION
    
    if text == 'нет':
        await update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
    
    # Обработка подтверждения для разных операций
    operation = context.user_data.get('pending_operation')
    
    if operation == 'issue':
        data = context.user_data['pending_data']
        success = True
        success &= sheets_helper.update_cell(data['row_num'], 3, data['room'])  # Комната
        success &= sheets_helper.update_cell(data['row_num'], 4, "Выдан")       # Статус
        success &= sheets_helper.update_cell(data['row_num'], 6, data['name'])  # Владелец
        success &= sheets_helper.update_cell(data['row_num'], 7, data['issue_date'])  # Checkin (дата выдачи)
        success &= sheets_helper.update_cell(data['row_num'], 8, data['return_date'])  # Checkout (дата возврата)
        success &= sheets_helper.update_cell(data['row_num'], 9, data['contact'])  # Контакты
        
        if success:
            await update.message.reply_text("Роутер успешно выдан!")
        else:
            await update.message.reply_text("Ошибка при обновлении таблицы.")
    
    elif operation == 'return':
        row_num = context.user_data['pending_row_num']
        success = True
        success &= sheets_helper.update_cell(row_num, 3, "")  # Очищаем комнату
        success &= sheets_helper.update_cell(row_num, 4, "Свободен")  # Статус
        success &= sheets_helper.update_cell(row_num, 6, "")  # Владелец
        success &= sheets_helper.update_cell(row_num, 7, "")  # Checkin (дата выдачи)
        success &= sheets_helper.update_cell(row_num, 8, "")  # Checkout (дата возврата)
        success &= sheets_helper.update_cell(row_num, 9, "")  # Контакты
        success &= sheets_helper.update_cell(row_num, 10, "")  # Комментарий
        
        if success:
            await update.message.reply_text("Роутер принят и теперь свободен.")
        else:
            await update.message.reply_text("Ошибка при обновлении таблицы.")
    
    elif operation == 'extend':
        row_num = context.user_data['pending_row_num']
        return_date = context.user_data['pending_data']['return_date']
        
        success = sheets_helper.update_cell(row_num, 8, return_date)  # Обновляем только checkout
        
        if success:
            await update.message.reply_text(f"Срок возврата продлен до {return_date}.")
        else:
            await update.message.reply_text("Ошибка при обновлении таблицы.")
    
    elif operation == 'add_comment':
        row_num = context.user_data['pending_row_num']
        comment = context.user_data['pending_comment']
        
        # Получаем текущий комментарий и добавляем новый
        current_comment = sheets_helper.sheet.cell(row_num, 10).value or ""
        if current_comment:
            new_comment = f"{current_comment}; {comment}"
        else:
            new_comment = comment
        
        success = sheets_helper.update_cell(row_num, 10, new_comment)
        
        if success:
            await update.message.reply_text("Комментарий успешно добавлен.")
        else:
            await update.message.reply_text("Ошибка при обновлении таблицы.")
    
    elif operation == 'change_owner':
        row_num = context.user_data['pending_row_num']
        data = context.user_data['pending_data']
        
        success = True
        success &= sheets_helper.update_cell(row_num, 6, data['name'])  # Владелец
        success &= sheets_helper.update_cell(row_num, 9, data['contact'])  # Контакты
        
        if success:
            await update.message.reply_text("Данные владельца успешно обновлены.")
        else:
            await update.message.reply_text("Ошибка при обновлении таблицы.")
    
    context.user_data.clear()
    return ConversationHandler.END

@restricted_access
async def update_statuses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет и обновляет статусы просроченных роутеров"""
    try:
        all_records = sheets_helper.get_all_records()
        current_date = datetime.now().date()
        updated_count = 0

        for i, record in enumerate(all_records, start=2):
            status = record.get('Status', '')
            checkout_str = record.get('Checkout', '')

            if status == 'Выдан' and checkout_str:
                try:
                    checkout_date = datetime.strptime(checkout_str, '%Y-%m-%d').date()
                    if checkout_date < current_date:
                        sheets_helper.update_cell(i, 4, 'Просрочен')
                        updated_count += 1
                except ValueError:
                    continue

        await update.message.reply_text(f"Проверка завершена. Обновлено статусов: {updated_count}.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении статусов: {e}")
        await update.message.reply_text("Произошла ошибка при обновлении статусов.")

@restricted_access
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет текущую операцию"""
    await update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END