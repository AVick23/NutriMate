"""
Утилиты для модуля сбора метрик и аналитики.
"""
import logging
from typing import Dict, Any
# Импортируем готовые функции из ядра аналитики, чтобы не дублировать код и избежать рассинхрона ключей
from analytics.core import get_default_metrics, format_metrics_summary, split_long_message

logger = logging.getLogger(__name__)

# Экспортируем их для локального использования в handlers
__all__ = ["get_default_metrics", "format_metrics_summary", "split_long_message"]