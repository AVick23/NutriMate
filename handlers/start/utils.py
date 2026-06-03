# handlers/start/utils.py
from typing import Optional
from datetime import datetime


def format_greeting(first_name: Optional[str] = None) -> str:
    """
    Форматирует приветствие в зависимости от времени суток.
    """
    now = datetime.now()
    hour = now.hour

    if 5 <= hour < 12:
        greeting = "Доброе утро"
    elif 12 <= hour < 18:
        greeting = "Добрый день"
    elif 18 <= hour < 23:
        greeting = "Добрый вечер"
    else:
        greeting = "Доброй ночи"

    name = first_name or "друг"
    
    return f"{greeting}, {name}! 🥑"


def get_weekday_name() -> str:
    """
    Возвращает название дня недели на русском.
    """
    weekdays = {
        0: "понедельник",
        1: "вторник", 
        2: "среда",
        3: "четверг",
        4: "пятница",
        5: "суббота",
        6: "воскресенье"
    }
    
    now = datetime.now()
    return weekdays[now.weekday()]


def get_month_name() -> str:
    """
    Возвращает название месяца на русском.
    """
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    
    now = datetime.now()
    return months[now.month]