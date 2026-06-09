"""
Клавиатуры для истории питания.
🎯 Обновлено: убран "Завтра", добавлены "Неделя/Месяц", "Повторить день",
   цветовые индикаторы в календаре.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict
from .constants import STATUS_GOOD, STATUS_WARNING, STATUS_BAD, STATUS_EMPTY


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    🎯 Главное меню выбора даты.
    Убрана кнопка "Завтра", добавлены "Неделя" и "Месяц".
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Вчера", callback_data="history_yesterday"),
            InlineKeyboardButton("📅 Сегодня", callback_data="history_today"),
        ],
        [
            InlineKeyboardButton("📊 Неделя", callback_data="history_week"),
            InlineKeyboardButton("📅 Месяц", callback_data="history_month"),
        ],
        [
            InlineKeyboardButton("📆 Другая дата", callback_data="history_other_date"),
        ],
        [
            InlineKeyboardButton("← Назад в дневник", callback_data="history_back_to_menu"),
        ],
    ])


def get_navigation_keyboard(target_date: date, has_entries: bool = False) -> InlineKeyboardMarkup:
    """
    🎯 Клавиатура навигации под историей.
    Убрана кнопка "Завтра", добавлена "🔁 Повторить день".
    """
    prev_date = target_date - timedelta(days=1)
    
    row1 = [
        InlineKeyboardButton("◀️ Вчера", callback_data=f"nav_{prev_date}"),
        InlineKeyboardButton("📅 Сегодня", callback_data="nav_today"),
    ]
    
    row2 = [InlineKeyboardButton("📆 Другая дата", callback_data="nav_other_date")]
    
    # 🎯 Кнопка "Повторить день" — только если есть записи
    if has_entries:
        row2.append(InlineKeyboardButton("🔁 Повторить день", callback_data="nav_repeat_day"))
    
    return InlineKeyboardMarkup([
        row1,
        row2,
        [
            InlineKeyboardButton("🍽️ Добавить еду", callback_data="nav_add_food"),
            InlineKeyboardButton("← В меню", callback_data="history_back_to_menu"),
        ],
    ])


def get_empty_history_keyboard(target_date: date) -> InlineKeyboardMarkup:
    """Клавиатура для дня без записей. Убрана кнопка "Завтра"."""
    prev_date = target_date - timedelta(days=1)
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Вчера", callback_data=f"nav_{prev_date}"),
            InlineKeyboardButton("📅 Сегодня", callback_data="nav_today"),
        ],
        [
            InlineKeyboardButton("📆 Другая дата", callback_data="nav_other_date"),
            InlineKeyboardButton("🍽️ Добавить еду", callback_data="nav_add_food"),
        ],
        [
            InlineKeyboardButton("← В меню", callback_data="history_back_to_menu"),
        ],
    ])


def get_calendar_keyboard(
    year: int,
    month: int,
    date_status: Dict[str, str],  # 🎯 НОВОЕ: {date_str: status}
    current_date: Optional[date] = None
) -> InlineKeyboardMarkup:
    """
    🎯 Генерирует клавиатуру-календарь с цветовыми индикаторами.
    
    🟢 — в норме
    🟡 — небольшое отклонение
    🔴 — сильное отклонение
    ⚪ — нет записей
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

    # Легенда
    legend_row = [
        InlineKeyboardButton("🟢✓", callback_data="noop"),
        InlineKeyboardButton("🟡~", callback_data="noop"),
        InlineKeyboardButton("🔴!", callback_data="noop"),
        InlineKeyboardButton("⚪—", callback_data="noop"),
    ]
    buttons.append(legend_row)

    # Дни недели
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    week_row = [InlineKeyboardButton(day, callback_data="noop") for day in weekdays]
    buttons.append(week_row)

    # Календарь с цветами
    cal = monthcalendar(year, month)
    today = date.today()
    
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                current_day = date(year, month, day)
                
                # Будущие дни — неактивны
                if current_day > today:
                    row.append(InlineKeyboardButton(" ", callback_data="noop"))
                    continue
                
                status = date_status.get(date_str, STATUS_EMPTY)
                
                # 🎯 Формируем текст с цветовым индикатором
                if status == STATUS_GOOD:
                    button_text = f"🟢{day}"
                elif status == STATUS_WARNING:
                    button_text = f"🟡{day}"
                elif status == STATUS_BAD:
                    button_text = f"🔴{day}"
                elif status == STATUS_EMPTY:
                    button_text = f"⚪{day}"
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
        InlineKeyboardButton(f"{month_name_ru[month]} {year}", callback_data="noop"),
        InlineKeyboardButton("▶️", callback_data=f"calendar_next_{year}_{month}"),
    ]
    buttons.append(nav_row)

    # Кнопка назад
    back_row = [
        InlineKeyboardButton("← Назад в меню", callback_data="calendar_back"),
    ]
    buttons.append(back_row)

    return InlineKeyboardMarkup(buttons)


def get_calendar_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для возврата из календаря."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("← Назад к выбору даты", callback_data="calendar_back")],
    ])


def get_period_summary_keyboard(period_days: int) -> InlineKeyboardMarkup:
    """
    🎯 Клавиатура для сводки за период.
    """
    buttons = []
    
    if period_days == 7:
        # Для недели — предлагаем посмотреть месяц
        buttons.append([
            InlineKeyboardButton("📅 Посмотреть месяц", callback_data="summary_to_month"),
        ])
    
    buttons.append([
        InlineKeyboardButton("← В меню истории", callback_data="summary_back"),
    ])
    buttons.append([
        InlineKeyboardButton("📔 В дневник", callback_data="history_back_to_menu"),
    ])
    
    return InlineKeyboardMarkup(buttons)


def get_repeat_confirmation_keyboard() -> InlineKeyboardMarkup:
    """🎯 Клавиатура подтверждения повтора дня."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, повторить", callback_data="repeat_confirm"),
            InlineKeyboardButton("❌ Отмена", callback_data="repeat_cancel"),
        ],
    ])