"""
Логирование действий в модуле метрик.
"""
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any

# Настройка логгера для метрик
metrics_logger = logging.getLogger("metrics_actions")
metrics_logger.setLevel(logging.INFO)

# Хэндлер для записи в файл
file_handler = logging.FileHandler("logs/metrics.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
metrics_logger.addHandler(file_handler)

# Опционально: вывод в консоль (можно закомментировать)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s", datefmt="%H:%M:%S"))
metrics_logger.addHandler(console_handler)


def log_metrics_action(user_id: int, action: str, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Логирует действие пользователя в разделе метрик.
    
    Args:
        user_id: Telegram ID пользователя
        action: Тип действия (open_menu, save_metric, start_full_session, etc.)
        details: Дополнительные данные (словарь)
    """
    log_entry = {
        "user_id": user_id,
        "action": action,
        "timestamp": datetime.now().isoformat(),
    }
    if details:
        log_entry["details"] = details
    
    metrics_logger.info(json.dumps(log_entry, ensure_ascii=False))