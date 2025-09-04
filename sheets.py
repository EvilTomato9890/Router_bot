# google_sheets.py
import logging
import re
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from config import SCOPES, SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, SHEET_NAME

logger = logging.getLogger(__name__)

class GoogleSheetsHelper:
    def __init__(self):
        self.sheet = None
        self.init_sheet()
    
    def init_sheet(self):
        """Инициализирует подключение к Google Таблице"""
        try:
            creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            self.sheet = spreadsheet.worksheet(SHEET_NAME)
            logger.info("Успешное подключение к Google Таблице")
        except Exception as e:
            logger.error(f"Ошибка подключения к Google Таблице: {e}")
            self.sheet = None
    
    def find_row_by_mac(self, mac_address):
        """Ищет строку по MAC-адресу"""
        if not self.sheet:
            return None, None
        
        try:
            mac_clean = mac_address.lower().replace('-', '').replace(':', '').replace(' ', '')
            all_macs = self.sheet.col_values(2)
            
            for i, mac in enumerate(all_macs, 1):
                current_mac_clean = mac.lower().replace('-', '').replace(':', '').replace(' ', '')
                if current_mac_clean == mac_clean:
                    return i, self.sheet.row_values(i)
            return None, None
        except Exception as e:
            logger.error(f"Ошибка при поиске по MAC: {e}")
            return None, None
    
    def find_row_by_room(self, room_number):
        """Ищет строку по номеру комнаты"""
        if not self.sheet:
            return None, None
        
        try:
            all_rooms = self.sheet.col_values(3)
            for i, room in enumerate(all_rooms, 1):
                if room.strip() == room_number.strip():
                    return i, self.sheet.row_values(i)
            return None, None
        except Exception as e:
            logger.error(f"Ошибка при поиске по комнате: {e}")
            return None, None
    
    def update_cell(self, row_num, col_num, value):
        """Обновляет ячейку в таблице"""
        if not self.sheet:
            return False
        
        try:
            self.sheet.update_cell(row_num, col_num, value)
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении таблица: {e}")
            return False
    
    def get_all_records(self):
        """Получает все записи из таблицы"""
        if not self.sheet:
            return []
        
        try:
            return self.sheet.get_all_records()
        except Exception as e:
            logger.error(f"Ошибка при получении записей: {e}")
            return []
    
    def get_router_info(self, row_data):
        """Форматирует информацию о роутере для отображения"""
        if len(row_data) < 9:
            return "Недостаточно данных о роутере"
        
        info = (
            f"MAC: {row_data[1] if len(row_data) > 1 else 'Н/Д'}\n"
            f"Комната: {row_data[2] if len(row_data) > 2 else 'Н/Д'}\n"
            f"Статус: {row_data[3] if len(row_data) > 3 else 'Н/Д'}\n"
            f"Владелец: {row_data[5] if len(row_data) > 5 else 'Н/Д'}\n"
            f"Контакты: {row_data[8] if len(row_data) > 8 else 'Н/Д'}\n"
            f"Комментарий: {row_data[9] if len(row_data) > 9 else 'Н/Д'}\n"
            f"Дата выдачи: {row_data[6] if len(row_data) > 6 else 'Н/Д'}\n"
            f"Вернуть до: {row_data[7] if len(row_data) > 7 else 'Н/Д'}"
        )
        return info

# Глобальный экземпляр для использования в других модулях
sheets_helper = GoogleSheetsHelper()