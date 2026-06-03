# handlers/history_of_add/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, date, timedelta
from calendar import month_name
from typing import List, Optional, Set


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню выбора даты."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Вчера", callback_data="history_yesterday"),
            InlineKeyboardButton("📅 Сегодня", callback_data="history_today"),
            InlineKeyboardButton("Завтра ▶️", callback_data="history_tomorrow"),
        ],
        [
            InlineKeyboardButton("📆 Другая дата", callback_data="history_other_date"),
        ],
        [
            InlineKeyboardButton("← Назад в меню", callback_data="history_back_to_menu"),
        ],
    ])


def get_navigation_keyboard(target_date: date) -> InlineKeyboardMarkup:
    """Клавиатура навигации под историей."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Вчера", callback_data=f"nav_{target_date - timedelta(days=1)}"),
            InlineKeyboardButton("📅 Сегодня", callback_data="nav_today"),
            InlineKeyboardButton("Завтра ▶️", callback_data=f"nav_{target_date + timedelta(days=1)}"),
        ],
        [
            InlineKeyboardButton("📆 Другая дата", callback_data="nav_other_date"),
        ],
        [
            InlineKeyboardButton("🍽️ Добавить еду", callback_data="nav_add_food"),
            InlineKeyboardButton("← Назад", callback_data="history_back_to_menu"),
        ],
    ])


def get_empty_history_keyboard(target_date: date) -> InlineKeyboardMarkup:
    """Клавиатура для дня без записей."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Вчера", callback_data=f"nav_{target_date - timedelta(days=1)}"),
            InlineKeyboardButton("📅 Сегодня", callback_data="nav_today"),
            InlineKeyboardButton("Завтра ▶️", callback_data=f"nav_{target_date + timedelta(days=1)}"),
        ],
        [
            InlineKeyboardButton("📆 Другая дата", callback_data="nav_other_date"),
            InlineKeyboardButton("🍽️ Добавить еду", callback_data="nav_add_food"),
        ],
        [
            InlineKeyboardButton("← Назад в меню", callback_data="history_back_to_menu"),
        ],
    ])


def get_calendar_keyboard(
    year: int,
    month: int,
    available_dates: Set[str],
    current_date: Optional[date] = None
) -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру-календарь.
    Подсвечивает даты, где есть записи (✓).
    """
    from calendar import monthcalendar
    
    buttons = []
    
    # Заголовок с месяцем и годом
    month_name_ru = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    title_row = [
        InlineKeyboardButton(
            f"{month_name_ru[month]} {year}",
            callback_data="noop"
        )
    ]
    buttons.append(title_row)
    
    # Дни недели
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    week_row = [InlineKeyboardButton(day, callback_data="noop") for day in weekdays]
    buttons.append(week_row)
    
    # Календарь
    cal = monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                has_entries = date_str in available_dates
                
                # Формируем текст кнопки
                if has_entries:
                    button_text = f"✓ {day}"
                else:
                    button_text = f"  {day}"
                
                row.append(
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"calendar_select_{date_str}"
                    )
                )
        buttons.append(row)
    
    # Навигация по месяцам
    nav_row = [
        InlineKeyboardButton("◀️", callback_data=f"calendar_prev_{year}_{month}"),
        InlineKeyboardButton("📅 Выбрать", callback_data="noop"),
        InlineKeyboardButton("▶️", callback_data=f"calendar_next_{year}_{month}"),
    ]
    buttons.append(nav_row)
    
    # Кнопка назад
    back_row = [
        InlineKeyboardButton("← Назад к выбору даты", callback_data="calendar_back"),
    ]
    buttons.append(back_row)
    
    return InlineKeyboardMarkup(buttons)


def get_calendar_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для возврата из календаря."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("← Назад к выбору даты", callback_data="calendar_back")],
    ])