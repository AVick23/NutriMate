"""
Логирование действий в модуле метрик.
Выводит логи прямо в терминал (консоль).
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any

# Используем стандартный логгер Python
# Он автоматически выводит всё в консоль (как настроено в main.py)
metrics_logger = logging.getLogger("metrics")


def log_metrics_action(
    user_id: int, 
    action: str, 
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Логирует действие пользователя в разделе метрик.
    
    Args:
        user_id: ID пользователя в БД
        action: Тип действия (open_menu, save_metric, start_full_session и т.д.)
        details: Дополнительные данные (словарь)
    """
    # Формируем человекочитаемое сообщение
    details_str = ""
    if details:
        # Компактно форматируем детали
        parts = [f"{k}={v}" for k, v in details.items() if v is not None]
        if parts:
            details_str = f" | {' | '.join(parts)}"
    
    metrics_logger.info(f"📊 [METRICS] user={user_id} | action={action}{details_str}")


def log_metrics_error(
    user_id: int,
    action: str,
    error: Exception,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Логирует ошибку в модуле метрик.
    """
    details_str = ""
    if details:
        parts = [f"{k}={v}" for k, v in details.items() if v is not None]
        if parts:
            details_str = f" | {' | '.join(parts)}"
    
    metrics_logger.error(
        f"❌ [METRICS ERROR] user={user_id} | action={action} | "
        f"error={type(error).__name__}: {error}{details_str}"
    )


def log_analytics_calc(
    user_id: int,
    calc_type: str,
    base_value: Any,
    adjusted_value: Any,
    modifiers: Optional[Dict[str, float]] = None
) -> None:
    """
    Логирует расчёт аналитики (TDEE, модификаторы).
    """
    mods_str = ""
    if modifiers:
        mods_parts = [f"{k}={v:.3f}" for k, v in modifiers.items() if isinstance(v, (int, float))]
        if mods_parts:
            mods_str = f" | mods=[{', '.join(mods_parts)}]"
    
    metrics_logger.info(
        f"🧮 [ANALYTICS] user={user_id} | type={calc_type} | "
        f"base={base_value} → adjusted={adjusted_value}{mods_str}"
    )