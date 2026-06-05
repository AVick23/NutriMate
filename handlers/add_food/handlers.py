"""
Обработчики для добавления еды с пагинацией, голосовым вводом,
улучшенным распознаванием штрихкодов и ручным вводом.

Избранное вынесено в отдельный модуль handlers/favorites/.
При нажатии "⭐️ Избранное" в меню еды — выходим отсюда
и попадаем в ConversationHandler избранного.
"""
import io
import logging
from typing import Optional, List, Dict, Any
from PIL import Image, ImageEnhance, ImageFilter
from pyzbar.pyzbar import decode
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CallbackQueryHandler, MessageHandler, filters
)

from db.database import Database
from db.repositories import (
    UserRepository, MealRepository,
    FavoritesRepository, DailyStatsRepository
)
from handlers.add_food.constants import (
    STATE_SELECT_METHOD, STATE_WAIT_FOR_TEXT, STATE_SELECT_PRODUCT,
    STATE_SELECT_MEAL_TYPE, STATE_ENTER_WEIGHT, STATE_CONFIRM_ADD,
    STATE_WAIT_FOR_BARCODE, STATE_AFTER_ADD, STATE_WAIT_FOR_VOICE,
    STATE_MANUAL_INPUT, STATE_MANUAL_NAME, STATE_MANUAL_WEIGHT,
    STATE_MANUAL_KCAL, STATE_MANUAL_PROTEIN, STATE_MANUAL_FAT,
    STATE_MANUAL_CARBS, STATE_MANUAL_CONFIRM,
    MEAL_TYPES, PAGE_SIZE,
    CALLBACK_METHOD_TEXT, CALLBACK_METHOD_BARCODE, CALLBACK_METHOD_FAVORITES,
    CALLBACK_METHOD_POPULAR, CALLBACK_METHOD_VOICE, CALLBACK_METHOD_MANUAL,
    CALLBACK_BACK_TO_DIARY, CALLBACK_BACK_TO_METHOD,
    CALLBACK_BACK_TO_TEXT, CALLBACK_BACK_TO_RESULTS, CALLBACK_BACK_TO_WEIGHT,
    CALLBACK_SEARCH_AGAIN, CALLBACK_SELECT_PRODUCT,
    CALLBACK_PAGE_PREV, CALLBACK_PAGE_NEXT,
    CALLBACK_WEIGHT_PREFIX, CALLBACK_WEIGHT_CUSTOM,
    CALLBACK_MEAL_PREFIX, CALLBACK_CONFIRM_ADD, CALLBACK_CHANGE_WEIGHT,
    CALLBACK_ADD_ANOTHER, CALLBACK_SAVE_FAVORITE_YES, CALLBACK_SAVE_FAVORITE_NO,
    CALLBACK_NOOP, CALLBACK_CANCEL, CALLBACK_MANUAL_SKIP,
    CALLBACK_MANUAL_CONFIRM, CALLBACK_MANUAL_EDIT,
)
from handlers.add_food.keyboards import (
    get_select_method_keyboard, get_text_input_keyboard, get_barcode_keyboard,
    get_meal_type_keyboard, get_product_selection_keyboard, get_weight_input_keyboard,
    get_confirm_keyboard, get_after_add_keyboard, get_save_favorite_keyboard,
    get_custom_weight_keyboard, get_voice_keyboard, get_manual_input_keyboard,
    get_manual_skip_keyboard, get_manual_confirm_keyboard,
)
from handlers.add_food.api_client import OpenFoodFactsClient
from handlers.add_food.food_matcher import OptimizedFoodMatcher
from handlers.add_food.local_foods import POPULAR_FOODS
from handlers.add_food.voice_recognizer import VoiceRecognizer
from handlers.add_food.utils import parse_manual_template, format_manual_product_for_confirmation

logger = logging.getLogger(__name__)


class AddFoodHandlers:
    """Все обработчики для добавления еды."""

    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.meal_repo = MealRepository(db)
        self.favorites_repo = FavoritesRepository(db)
        self.api_client = OpenFoodFactsClient()
        self.food_matcher = OptimizedFoodMatcher(POPULAR_FOODS, self.api_client)
        self.voice_recognizer = VoiceRecognizer()

    # ================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ================================================================

    def _get_search_context(self, context: ContextTypes.DEFAULT_TYPE) -> dict:
        """Получает контекст поиска."""
        return {
            "results": context.user_data.get("search_results", []),
            "page": context.user_data.get("search_page", 0),
            "query": context.user_data.get("food_search_query", ""),
        }

    def _clear_search_context(self, context: ContextTypes.DEFAULT_TYPE):
        """Очищает временные данные поиска, НО сохраняет метод поиска."""
        saved_method = context.user_data.get("search_method")

        for key in [
            "search_results", "search_page", "selected_product",
            "calculated_food", "meal_type", "food_weight",
            "last_added_food", "food_search_query",
        ]:
            context.user_data.pop(key, None)

        if saved_method:
            context.user_data["search_method"] = saved_method

    def _format_products_text(self, products: List[Dict[str, Any]], start_idx: int = 0) -> str:
        """Форматирует список продуктов с полным КБЖУ для отображения в сообщении."""
        text = ""
        text += "─" * 17 + "\n"

        for i, product in enumerate(products):
            real_index = start_idx + i
            name = product["name"][:40]
            brand = f" ({product.get('brand', '')})" if product.get("brand") else ""
            kcal = product.get("kcal_100g", 0)
            protein = product.get("protein_100g", 0)
            fat = product.get("fat_100g", 0)
            carbs = product.get("carbs_100g", 0)

            text += f"<b>{real_index + 1}</b> {name}{brand}\n"
            text += f"🔥 {kcal:.0f} ккал | 🍗 {protein:.1f}г | 🥑 {fat:.1f}г | 🍚 {carbs:.1f}г\n\n"

        text += "─" * 17 + "\n"
        return text

    # ================================================================
    # ВХОДНАЯ ТОЧКА
    # ================================================================

    async def show_add_food_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает меню выбора способа добавления еды."""
        query = update.callback_query
        if query:
            await query.answer()

        # Полный сброс контекста (включая метод поиска)
        for key in [
            "search_results", "search_page", "selected_product",
            "calculated_food", "meal_type", "food_weight",
            "last_added_food", "food_search_query", "search_method",
            "manual_product",
        ]:
            context.user_data.pop(key, None)

        text = (
            "🍽️ <b>Добавление еды</b>\n\n"
            "Выбери, как удобнее записать приём пищи."
        )

        target = query.edit_message_text if query else update.message.reply_text
        await target(
            text,
            reply_markup=get_select_method_keyboard(),
            parse_mode="HTML"
        )
        return STATE_SELECT_METHOD

    async def handle_method_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор способа добавления."""
        query = update.callback_query
        await query.answer()

        method = query.data

        if method == CALLBACK_METHOD_TEXT:
            return await self._start_text_input(update, context)
        elif method == CALLBACK_METHOD_BARCODE:
            return await self._start_barcode_scan(update, context)
        elif method == CALLBACK_METHOD_FAVORITES:
            # 🎯 ВЫХОД В ВНЕШНИЙ МОДУЛЬ ИЗБРАННОГО
            # Завершаем текущий ConversationHandler и передаём управление
            # в handlers/favorites/ через прямой вызов
            self._clear_search_context(context)
            context.user_data.pop("search_method", None)

            from handlers.favorites.handlers import FavoritesHandlers
            fav_handler = FavoritesHandlers(self.db)
            await fav_handler.show_favorites_menu(update, context)
            return ConversationHandler.END
        elif method == CALLBACK_METHOD_POPULAR:
            return await self._show_popular_foods(update, context)
        elif method == CALLBACK_METHOD_VOICE:
            return await self._start_voice_input(update, context)
        elif method == CALLBACK_METHOD_MANUAL:
            return await self._start_manual_input(update, context)
        elif method == CALLBACK_BACK_TO_DIARY:
            return await self._back_to_diary(update, context)

        return STATE_SELECT_METHOD

    # ================================================================
    # ПОПУЛЯРНЫЕ БЛЮДА
    # ================================================================

    async def _show_popular_foods(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает популярные блюда с пагинацией и полным КБЖУ."""
        query = update.callback_query
        await query.answer()

        context.user_data["search_method"] = "popular"
        context.user_data["search_results"] = POPULAR_FOODS
        context.user_data["search_page"] = 0
        context.user_data["food_search_query"] = "Популярные блюда"

        total = len(POPULAR_FOODS)
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

        text = (
            f"🔥 <b>Популярные блюда</b>\n\n"
            f"Всего: {total} блюд\n"
            f"Страница 1 из {pages}\n\n"
        )

        text += self._format_products_text(POPULAR_FOODS[:PAGE_SIZE], start_idx=0)
        text += "Выбери блюдо из списка:"

        await query.edit_message_text(
            text,
            reply_markup=get_product_selection_keyboard(
                POPULAR_FOODS, page=0, query="Популярные блюда"
            ),
            parse_mode="HTML"
        )
        return STATE_SELECT_PRODUCT

    # ================================================================
    # ТЕКСТОВЫЙ ПОИСК
    # ================================================================

    async def _start_text_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает текстовый поиск."""
        query = update.callback_query
        if query:
            await query.answer()

        context.user_data["search_method"] = "text"

        prev_query = context.user_data.get("food_search_query", "")
        hint = f'\n\n💡 <i>Прошлый запрос: «{prev_query}»</i>' if prev_query else ""

        text = (
            "✍️ <b>Опиши, что ты съел</b>\n\n"
            "Напиши одним сообщением название и (по возможности) вес.\n\n"
            "<b>Примеры:</b>\n"
            "• <code>гречка с котлетой 300г</code>\n"
            "• <code>омлет из двух яиц</code>\n"
            "• <code>банан</code>"
            f"{hint}"
        )

        target = query.edit_message_text if query else update.message.reply_text
        await target(
            text,
            reply_markup=get_text_input_keyboard(),
            parse_mode="HTML"
        )
        return STATE_WAIT_FOR_TEXT

    async def process_text_search(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает текстовый запрос с пагинацией и полным КБЖУ."""
        user_input = update.message.text.strip()

        food_name, weight, unit = self.food_matcher.parse_quantity_from_text(user_input)

        if unit and unit != 'г':
            weight = None

        context.user_data["food_search_query"] = food_name
        if weight:
            context.user_data["food_weight"] = weight

        status_msg = await update.message.reply_text(
            "🔍 <b>Ищу продукты...</b>",
            parse_mode="HTML"
        )

        products = await self.food_matcher.search_with_api_fallback(food_name)

        if not products:
            await status_msg.edit_text(
                f"❌ По запросу <i>«{food_name}»</i> ничего не найдено.\n\n"
                "Попробуй:\n"
                "• Написать по-другому\n"
                "• Проверить опечатки\n"
                "• Убрать уточнения",
                reply_markup=get_text_input_keyboard(),
                parse_mode="HTML"
            )
            return STATE_WAIT_FOR_TEXT

        context.user_data["search_results"] = products
        context.user_data["search_page"] = 0

        total = len(products)
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

        text = (
            f"🔍 <b>Найдено: {total} продуктов</b>\n"
            f"Запрос: <i>«{food_name}»</i>\n"
            f"Страница 1 из {pages}\n\n"
        )

        text += self._format_products_text(products[:PAGE_SIZE], start_idx=0)
        text += "Выбери подходящий вариант:"

        await status_msg.delete()
        await update.message.reply_text(
            text,
            reply_markup=get_product_selection_keyboard(products, page=0, query=food_name),
            parse_mode="HTML"
        )

        return STATE_SELECT_PRODUCT

    # ================================================================
    # ВЫБОР ПРОДУКТА И ПАГИНАЦИЯ
    # ================================================================

    async def select_product(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор продукта."""
        query = update.callback_query
        await query.answer("✓ Выбрано")

        data = query.data
        try:
            index = int(data.replace(CALLBACK_SELECT_PRODUCT, ""))
        except ValueError:
            return STATE_SELECT_PRODUCT

        products = context.user_data.get("search_results", [])
        if index >= len(products):
            await query.answer("❌ Продукт не найден", show_alert=True)
            return STATE_SELECT_PRODUCT

        selected = products[index]
        context.user_data["selected_product"] = selected

        if "food_weight" in context.user_data:
            weight = context.user_data["food_weight"]
            calculated = self.api_client.calculate_for_weight(selected, weight)
            context.user_data["calculated_food"] = calculated
            return await self._ask_meal_type(update, context)

        return await self._ask_weight(update, context)

    async def handle_pagination(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает пагинацию результатов с полным КБЖУ."""
        query = update.callback_query
        await query.answer()

        ctx = self._get_search_context(context)
        results = ctx["results"]
        current_page = ctx["page"]
        total_pages = max(1, (len(results) + PAGE_SIZE - 1) // PAGE_SIZE)

        if query.data == CALLBACK_PAGE_PREV:
            new_page = max(0, current_page - 1)
        elif query.data == CALLBACK_PAGE_NEXT:
            new_page = min(total_pages - 1, current_page + 1)
        else:
            return STATE_SELECT_PRODUCT

        context.user_data["search_page"] = new_page

        start_idx = new_page * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        page_products = results[start_idx:end_idx]

        text = (
            f"🔍 <b>Найдено: {len(results)} продуктов</b>\n"
            f"Запрос: <i>«{ctx['query']}»</i>\n"
            f"Страница {new_page + 1} из {total_pages}\n\n"
        )

        text += self._format_products_text(page_products, start_idx=start_idx)
        text += "Выбери подходящий вариант:"

        await query.edit_message_text(
            text,
            reply_markup=get_product_selection_keyboard(
                results, page=new_page, query=ctx["query"]
            ),
            parse_mode="HTML"
        )

        return STATE_SELECT_PRODUCT

    # ================================================================
    # ВЫБОР ВЕСА
    # ================================================================

    async def _ask_weight(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает вес продукта."""
        query = update.callback_query
        if query:
            await query.answer()

        product = context.user_data.get("selected_product", {})
        default_weight = product.get("default_weight", 100)
        name = product.get("name", "")[:40]

        text = (
            f"⚖️ <b>Сколько грамм?</b>\n\n"
            f"🍽 <b>{name}</b>\n"
            f"💡 Обычно: ~{default_weight:.0f}г\n\n"
            "Выбери из вариантов или введи свой."
        )

        target = query.edit_message_text if query else update.message.reply_text
        await target(
            text,
            reply_markup=get_weight_input_keyboard(name),
            parse_mode="HTML"
        )
        return STATE_ENTER_WEIGHT

    async def process_weight_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор веса."""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == CALLBACK_BACK_TO_RESULTS:
            return await self._back_to_results(update, context)

        if data == CALLBACK_SEARCH_AGAIN:
            return await self._search_again(update, context)

        if data == CALLBACK_WEIGHT_CUSTOM:
            await query.edit_message_text(
                "✏️ <b>Введи вес в граммах</b>\n\n"
                "Только число, например: <code>150</code>",
                reply_markup=get_custom_weight_keyboard(),
                parse_mode="HTML"
            )
            return STATE_ENTER_WEIGHT

        if data.startswith(CALLBACK_WEIGHT_PREFIX):
            try:
                weight = float(data.replace(CALLBACK_WEIGHT_PREFIX, ""))
            except ValueError:
                return STATE_ENTER_WEIGHT

            product = context.user_data.get("selected_product", {})
            calculated = self.api_client.calculate_for_weight(product, weight)
            context.user_data["calculated_food"] = calculated
            return await self._ask_meal_type(update, context)

        return STATE_ENTER_WEIGHT

    async def process_custom_weight(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает ручной ввод веса."""
        user_input = update.message.text.strip()

        try:
            weight = float(user_input.replace(",", "."))
            if weight <= 0 or weight > 10000:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Введи число от 1 до 10000 грамм.\n"
                "Например: <code>150</code>",
                reply_markup=get_custom_weight_keyboard(),
                parse_mode="HTML"
            )
            return STATE_ENTER_WEIGHT

        product = context.user_data.get("selected_product", {})
        calculated = self.api_client.calculate_for_weight(product, weight)
        context.user_data["calculated_food"] = calculated

        await self._ask_meal_type_message(update, context)
        return STATE_SELECT_MEAL_TYPE

    # ================================================================
    # ТИП ПРИЁМА ПИЩИ
    # ================================================================

    async def _ask_meal_type(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает тип приёма пищи (callback)."""
        query = update.callback_query
        if query:
            await query.answer()

        calculated = context.user_data.get("calculated_food", {})
        text = self._format_meal_type_text(calculated)

        target = query.edit_message_text if query else update.message.reply_text
        await target(
            text,
            reply_markup=get_meal_type_keyboard(),
            parse_mode="HTML"
        )
        return STATE_SELECT_MEAL_TYPE

    async def _ask_meal_type_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Спрашивает тип приёма пищи (message)."""
        calculated = context.user_data.get("calculated_food", {})
        text = self._format_meal_type_text(calculated)

        await update.message.reply_text(
            text,
            reply_markup=get_meal_type_keyboard(),
            parse_mode="HTML"
        )

    def _format_meal_type_text(self, calculated: dict) -> str:
        """Форматирует текст для выбора типа приёма пищи."""
        return (
            f"🍽️ <b>Когда ты это съел?</b>\n\n"
            f"🍳 <b>{calculated.get('name', '')}</b>\n"
            f"⚖️ {calculated.get('weight', 0):.0f}г\n\n"
            f"🔥 {calculated.get('kcal', 0)} ккал · "
            f"🍗 {calculated.get('protein', 0):.1f}г · "
            f"🥑 {calculated.get('fat', 0):.1f}г · "
            f"🍚 {calculated.get('carbs', 0):.1f}г"
        )

    async def process_meal_type(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор типа приёма пищи."""
        query = update.callback_query
        await query.answer()

        if query.data == CALLBACK_BACK_TO_WEIGHT:
            return await self._ask_weight(update, context)
        if query.data == CALLBACK_SEARCH_AGAIN:
            return await self._search_again(update, context)

        meal_type = query.data.replace(CALLBACK_MEAL_PREFIX, "")
        context.user_data["meal_type"] = meal_type

        calculated = context.user_data.get("calculated_food", {})
        meal_label = MEAL_TYPES.get(meal_type, meal_type)

        text = (
            f"✅ <b>Проверь данные</b>\n\n"
            f"🍳 <b>{calculated.get('name', '')}</b>\n"
            f"⚖️ {calculated.get('weight', 0):.0f}г\n"
            f"🍽 {meal_label}\n\n"
            f"🔥 {calculated.get('kcal', 0)} ккал · "
            f"🍗 {calculated.get('protein', 0):.1f}г · "
            f"🥑 {calculated.get('fat', 0):.1f}г · "
            f"🍚 {calculated.get('carbs', 0):.1f}г\n\n"
            "Всё верно?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_confirm_keyboard(),
            parse_mode="HTML"
        )
        return STATE_CONFIRM_ADD

    # ================================================================
    # ПОДТВЕРЖДЕНИЕ И СОХРАНЕНИЕ
    # ================================================================

    async def confirm_add(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Подтверждает и сохраняет блюдо."""
        query = update.callback_query
        await query.answer("✓ Сохраняю...")

        data = query.data

        if data == CALLBACK_CHANGE_WEIGHT:
            return await self._ask_weight(update, context)
        if data == CALLBACK_SEARCH_AGAIN:
            return await self._search_again(update, context)
        if data == CALLBACK_BACK_TO_DIARY:
            return await self._back_to_diary(update, context)

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)

        calculated = context.user_data.get("calculated_food", {})
        meal_type = context.user_data.get("meal_type", "snack")
        selected = context.user_data.get("selected_product", {})

        await self.meal_repo.add_meal(
            user_id=user_id,
            meal_type=meal_type,
            food_name=calculated["name"],
            amount_g=calculated["weight"],
            kcal=calculated["kcal"],
            protein_g=calculated["protein"],
            fat_g=calculated["fat"],
            carbs_g=calculated["carbs"],
            barcode=selected.get("code")
        )

        meal_label = MEAL_TYPES.get(meal_type, meal_type)

        context.user_data["last_added_food"] = {
            "name": calculated["name"],
            "amount_g": calculated["weight"],
            "kcal": calculated["kcal"],
            "protein_g": calculated["protein"],
            "fat_g": calculated["fat"],
            "carbs_g": calculated["carbs"],
            "barcode": selected.get("code"),
        }

        text = (
            f"✅ <b>Добавлено в {meal_label}!</b>\n\n"
            f"🍳 <b>{calculated['name']}</b>\n"
            f"⚖️ {calculated['weight']:.0f}г\n"
            f"🔥 {calculated['kcal']} ккал\n\n"
            "Сохранить в избранное?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_save_favorite_keyboard(),
            parse_mode="HTML"
        )
        return STATE_CONFIRM_ADD

    async def handle_save_favorite(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает сохранение в избранное и переход в STATE_AFTER_ADD."""
        query = update.callback_query
        await query.answer()

        data = query.data
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)

        food_data = context.user_data.get("last_added_food", {})

        if data == CALLBACK_SAVE_FAVORITE_YES and food_data:
            await self.favorites_repo.add_favorite(
                user_id=user_id,
                food_name=food_data["name"],
                amount_g=food_data["amount_g"],
                kcal=food_data["kcal"],
                protein_g=food_data["protein_g"],
                fat_g=food_data["fat_g"],
                carbs_g=food_data["carbs_g"],
                barcode=food_data.get("barcode")
            )
            await query.answer("⭐ Сохранено в избранное!", show_alert=False)

        last_food = context.user_data.get("last_added_food", {})

        text = (
            f"🎉 <b>Готово!</b>\n\n"
            f"🍳 {last_food.get('name', 'Блюдо')} добавлено.\n\n"
            "Что хочешь сделать?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_after_add_keyboard(),
            parse_mode="HTML"
        )

        return STATE_AFTER_ADD

    # ================================================================
    # СОСТОЯНИЕ ПОСЛЕ ДОБАВЛЕНИЯ
    # ================================================================

    async def handle_after_add(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает действия после успешного добавления."""
        query = update.callback_query
        await query.answer()

        data = query.data
        context.user_data.pop("last_added_food", None)

        if data == CALLBACK_ADD_ANOTHER:
            return await self.show_add_food_menu(update, context)

        if data == CALLBACK_SEARCH_AGAIN:
            return await self._search_again(update, context)

        if data == CALLBACK_BACK_TO_DIARY:
            return await self._back_to_diary(update, context)

        return STATE_AFTER_ADD

    # ================================================================
    # ШТРИХКОД (УЛУЧШЕННЫЙ)
    # ================================================================

    async def _start_barcode_scan(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает сканирование штрихкода."""
        query = update.callback_query
        await query.answer()

        text = (
            "📷 <b>Сканирование штрихкода</b>\n\n"
            "Отправь мне <b>фото штрихкода</b> крупным планом.\n\n"
            "💡 <i>Или введи цифры с упаковки вручную.</i>"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_barcode_keyboard(),
            parse_mode="HTML"
        )
        return STATE_WAIT_FOR_BARCODE

    async def process_barcode(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает штрихкод (фото или текст)."""
        if update.message.photo:
            status_msg = await update.message.reply_text("🔍 Распознаю штрихкод...")
            barcode = await self._decode_barcode_from_photo(update, context)

            if not barcode:
                await status_msg.edit_text(
                    "❌ Не удалось распознать.\n\n"
                    "Попробуй:\n"
                    "• Сделать фото крупным планом\n"
                    "• Улучшить освещение\n"
                    "• Ввести цифры вручную",
                    reply_markup=get_barcode_keyboard(),
                    parse_mode="HTML"
                )
                return STATE_WAIT_FOR_BARCODE

            await status_msg.edit_text(
                f"✅ Штрихкод: <code>{barcode}</code>",
                parse_mode="HTML"
            )
        else:
            barcode = update.message.text.strip()
            if not barcode.isdigit() or len(barcode) < 8:
                await update.message.reply_text(
                    "❌ Это не похоже на штрихкод.\n"
                    "Должно быть 8-14 цифр.",
                    parse_mode="HTML"
                )
                return STATE_WAIT_FOR_BARCODE

        status_msg = await update.message.reply_text("🔍 Ищу продукт в базе...")
        product = await self.api_client.get_product_by_barcode(barcode)

        if not product:
            await status_msg.edit_text(
                f"❌ Продукт со штрихкодом <code>{barcode}</code> не найден.\n\n"
                "Попробуй найти через текстовый поиск.",
                reply_markup=get_barcode_keyboard(),
                parse_mode="HTML"
            )
            return STATE_WAIT_FOR_BARCODE

        context.user_data["selected_product"] = product
        context.user_data["search_results"] = [product]
        context.user_data["search_page"] = 0

        await status_msg.delete()

        text = (
            f"✅ <b>Продукт найден!</b>\n\n"
            f"🍽 <b>{product['name']}</b>\n"
            f"🔥 {product.get('kcal_100g', 0):.0f} ккал / 100г\n\n"
            "Сколько грамм ты съел?"
        )

        await update.message.reply_text(
            text,
            reply_markup=get_weight_input_keyboard(product['name']),
            parse_mode="HTML"
        )

        return STATE_ENTER_WEIGHT

    async def _decode_barcode_from_photo(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> Optional[str]:
        """Улучшенное распознавание штрихкода с preprocessing."""
        try:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_bytes = await file.download_as_bytearray()

            image = Image.open(io.BytesIO(file_bytes))

            if image.mode in ('RGBA', 'P'):
                image = image.convert('RGB')

            variants = self._preprocess_barcode_image(image)

            for processed_image in variants:
                decoded_objects = decode(processed_image)

                for obj in decoded_objects:
                    try:
                        barcode = obj.data.decode("ascii")
                        if self._validate_barcode(barcode):
                            logger.info(f"✅ Распознан штрихкод: {barcode}")
                            return barcode
                    except Exception:
                        continue

            logger.warning("Не удалось распознать штрихкод")
            return None

        except Exception as e:
            logger.error(f"Ошибка распознавания: {e}")
            return None

    def _preprocess_barcode_image(self, image: Image.Image) -> List[Image.Image]:
        """Создаёт варианты изображения для повышения шансов распознавания."""
        variants = [image]

        try:
            gray = image.convert('L')
            enhanced = ImageEnhance.Contrast(gray).enhance(2.0)
            enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.5)
            variants.append(enhanced)
        except Exception:
            pass

        try:
            gray = image.convert('L')
            sharpened = gray.filter(ImageFilter.SHARPEN)
            variants.append(sharpened)
        except Exception:
            pass

        for angle in [90, 180, 270]:
            try:
                rotated = image.rotate(angle, expand=True)
                variants.append(rotated)
            except Exception:
                continue

        return variants

    def _validate_barcode(self, barcode: str) -> bool:
        """Валидация формата штрихкода."""
        if not barcode.isdigit():
            return False
        if len(barcode) not in [8, 12, 13, 14]:
            return False
        if len(barcode) == 13:
            return self._verify_ean13_checksum(barcode)
        return True

    def _verify_ean13_checksum(self, barcode: str) -> bool:
        """Проверяет контрольную сумму EAN-13."""
        try:
            digits = [int(d) for d in barcode]
            weighted_sum = sum(
                digits[i] * (1 if i % 2 == 0 else 3)
                for i in range(12)
            )
            check_digit = (10 - (weighted_sum % 10)) % 10
            return check_digit == digits[12]
        except Exception:
            return False

    # ================================================================
    # ГОЛОСОВОЙ ВВОД
    # ================================================================

    async def _start_voice_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает ожидание голосового сообщения."""
        query = update.callback_query
        await query.answer()

        context.user_data["search_method"] = "voice"

        text = (
            "🎤 <b>Голосовой ввод</b>\n\n"
            "Просто нажми на 🎤 внизу и скажи, что ты съел.\n\n"
            "<b>Примеры:</b>\n"
            "• <i>«Гречка с котлетой триста грамм»</i>\n"
            "• <i>«Омлет из двух яиц»</i>\n"
            "• <i>«Банан»</i>\n\n"
            "Я пойму и всё посчитаю! 🧠"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_voice_keyboard(),
            parse_mode="HTML"
        )
        return STATE_WAIT_FOR_VOICE

    async def process_voice_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает голосовое сообщение."""
        status_msg = await update.message.reply_text(
            "👂 <b>Слушаю...</b>\n\nРаспознаю твоё голосовое сообщение...",
            parse_mode="HTML"
        )

        recognized_text = await self.voice_recognizer.recognize(update, context)

        if not recognized_text:
            await status_msg.edit_text(
                "❌ <b>Не удалось распознать</b>\n\n"
                "Попробуй ещё раз:\n"
                "• Говори чётко и не слишком быстро\n"
                "• Избегай фонового шума\n"
                "• Или напиши текстом",
                reply_markup=get_voice_keyboard(),
                parse_mode="HTML"
            )
            return STATE_WAIT_FOR_VOICE

        await status_msg.edit_text(
            f"🎤 <b>Я услышал:</b>\n"
            f"<i>«{recognized_text}»</i>\n\n"
            "🔍 Ищу продукты...",
            parse_mode="HTML"
        )

        food_name, weight, unit = self.food_matcher.parse_quantity_from_text(recognized_text)

        context.user_data["food_search_query"] = food_name
        if weight and (not unit or unit == 'г'):
            context.user_data["food_weight"] = weight

        products = await self.food_matcher.search_with_api_fallback(food_name)

        if not products:
            await update.message.reply_text(
                f"❌ По запросу <i>«{food_name}»</i> ничего не найдено.\n\n"
                "Попробуй произнести ещё раз или написать текстом.",
                reply_markup=get_voice_keyboard(),
                parse_mode="HTML"
            )
            return STATE_WAIT_FOR_VOICE

        context.user_data["search_results"] = products
        context.user_data["search_page"] = 0

        total = len(products)
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

        text = (
            f"🎤 <b>Услышал:</b> <i>«{recognized_text}»</i>\n"
            f"🔍 <b>Нашёл: {total} продуктов</b>\n"
            f"Страница 1 из {pages}\n\n"
        )

        text += self._format_products_text(products[:PAGE_SIZE], start_idx=0)
        text += "Выбери подходящий вариант:"

        await update.message.reply_text(
            text,
            reply_markup=get_product_selection_keyboard(
                products, page=0, query=food_name
            ),
            parse_mode="HTML"
        )

        return STATE_SELECT_PRODUCT

    # ================================================================
    # РУЧНОЙ ВВОД
    # ================================================================

    async def _start_manual_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает ручной ввод продукта."""
        query = update.callback_query
        if query:
            await query.answer()

        context.user_data["search_method"] = "manual"

        text = (
            "➕ <b>Ручной ввод продукта</b>\n\n"
            "Отправь данные в свободном формате:\n\n"
            "<b>Пример:</b>\n"
            "<code>Гречка с котлетой\n"
            "350г\n"
            "578 ккал\n"
            "Б: 33.3 Ж: 28.7 У: 49</code>\n\n"
            "Или в одну строку:\n"
            "<code>Гречка 350г 578ккал Б33 Ж28 У49</code>\n\n"
            "<i>Я пойму и посчитаю всё сам! 🧠</i>"
        )

        target = query.edit_message_text if query else update.message.reply_text
        await target(
            text,
            reply_markup=get_manual_input_keyboard(),
            parse_mode="HTML"
        )
        return STATE_MANUAL_INPUT

    async def process_manual_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        🎯 Обрабатывает ручной ввод.
        Пытается распознать шаблон, если не получилось — переходит к поэтапному вводу.
        """
        user_input = update.message.text.strip()

        # Пытаемся распознать шаблон
        parsed = parse_manual_template(user_input)

        if parsed:
            # 🎯 Магия: бот понял всё с первого раза!
            context.user_data["manual_product"] = parsed
            return await self._show_manual_confirmation(update, context)
        else:
            # Не получилось — переходим к поэтапному вводу
            await update.message.reply_text(
                "🤔 Не совсем понял формат. Давай введём по шагам!\n\n"
                "<b>Шаг 1/6:</b> Как называется продукт?",
                parse_mode="HTML"
            )
            return STATE_MANUAL_NAME

    async def process_manual_name(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает ввод названия."""
        name = update.message.text.strip()

        if not name:
            await update.message.reply_text(
                "❌ Название не может быть пустым. Попробуй ещё раз:",
                parse_mode="HTML"
            )
            return STATE_MANUAL_NAME

        context.user_data["manual_product"] = {
            "name": name,
            "weight": 100.0,
            "kcal": None,
            "protein": 0.0,
            "fat": 0.0,
            "carbs": 0.0,
        }

        await update.message.reply_text(
            f"✅ <b>{name}</b>\n\n"
            "<b>Шаг 2/6:</b> Какой вес порции (в граммах)?\n"
            "<i>Или нажми 'Пропустить' (будет 100г)</i>",
            reply_markup=get_manual_skip_keyboard(),
            parse_mode="HTML"
        )
        return STATE_MANUAL_WEIGHT

    async def process_manual_weight(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает ввод веса."""
        # Если нажали "Пропустить"
        if update.callback_query and update.callback_query.data == CALLBACK_MANUAL_SKIP:
            await update.callback_query.answer("⏭ Пропущено (100г)")
            return await self._ask_manual_kcal(update, context)

        # Парсим число
        try:
            weight = float(update.message.text.strip().replace(',', '.'))
            if weight <= 0 or weight > 10000:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Введи число от 1 до 10000 грамм.\n"
                "Например: <code>350</code>",
                parse_mode="HTML"
            )
            return STATE_MANUAL_WEIGHT

        context.user_data["manual_product"]["weight"] = weight
        return await self._ask_manual_kcal(update, context)

    async def _ask_manual_kcal(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает калории."""
        product = context.user_data.get("manual_product", {})
        name = product.get("name", "")

        target = update.callback_query.edit_message_text if update.callback_query else update.message.reply_text
        await target(
            f"✅ Вес: <b>{product['weight']:.0f}г</b>\n\n"
            f"<b>Шаг 3/6:</b> Сколько калорий в <b>{name}</b>?",
            parse_mode="HTML"
        )
        return STATE_MANUAL_KCAL

    async def process_manual_kcal(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает ввод калорий."""
        try:
            kcal = int(float(update.message.text.strip().replace(',', '.')))
            if kcal <= 0 or kcal > 5000:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Введи число от 1 до 5000 ккал.\n"
                "Например: <code>578</code>",
                parse_mode="HTML"
            )
            return STATE_MANUAL_KCAL

        context.user_data["manual_product"]["kcal"] = kcal
        return await self._ask_manual_protein(update, context)

    async def _ask_manual_protein(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает белки."""
        await update.message.reply_text(
            f"✅ Калории: <b>{context.user_data['manual_product']['kcal']} ккал</b>\n\n"
            "<b>Шаг 4/6:</b> Сколько белков (в граммах)?\n"
            "<i>Или нажми 'Пропустить'</i>",
            reply_markup=get_manual_skip_keyboard(),
            parse_mode="HTML"
        )
        return STATE_MANUAL_PROTEIN

    async def process_manual_protein(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает ввод белков."""
        if update.callback_query and update.callback_query.data == CALLBACK_MANUAL_SKIP:
            await update.callback_query.answer("⏭ Пропущено")
            return await self._ask_manual_fat(update, context)

        try:
            protein = float(update.message.text.strip().replace(',', '.'))
            if protein < 0 or protein > 1000:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Введи число от 0 до 1000 грамм.\n"
                "Например: <code>33.3</code>",
                parse_mode="HTML"
            )
            return STATE_MANUAL_PROTEIN

        context.user_data["manual_product"]["protein"] = protein
        return await self._ask_manual_fat(update, context)

    async def _ask_manual_fat(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает жиры."""
        target = update.callback_query.edit_message_text if update.callback_query else update.message.reply_text
        await target(
            f"✅ Белки: <b>{context.user_data['manual_product']['protein']:.1f}г</b>\n\n"
            "<b>Шаг 5/6:</b> Сколько жиров (в граммах)?\n"
            "<i>Или нажми 'Пропустить'</i>",
            reply_markup=get_manual_skip_keyboard(),
            parse_mode="HTML"
        )
        return STATE_MANUAL_FAT

    async def process_manual_fat(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает ввод жиров."""
        if update.callback_query and update.callback_query.data == CALLBACK_MANUAL_SKIP:
            await update.callback_query.answer("⏭ Пропущено")
            return await self._ask_manual_carbs(update, context)

        try:
            fat = float(update.message.text.strip().replace(',', '.'))
            if fat < 0 or fat > 1000:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Введи число от 0 до 1000 грамм.\n"
                "Например: <code>28.7</code>",
                parse_mode="HTML"
            )
            return STATE_MANUAL_FAT

        context.user_data["manual_product"]["fat"] = fat
        return await self._ask_manual_carbs(update, context)

    async def _ask_manual_carbs(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает углеводы."""
        target = update.callback_query.edit_message_text if update.callback_query else update.message.reply_text
        await target(
            f"✅ Жиры: <b>{context.user_data['manual_product']['fat']:.1f}г</b>\n\n"
            "<b>Шаг 6/6:</b> Сколько углеводов (в граммах)?\n"
            "<i>Или нажми 'Пропустить'</i>",
            reply_markup=get_manual_skip_keyboard(),
            parse_mode="HTML"
        )
        return STATE_MANUAL_CARBS

    async def process_manual_carbs(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает ввод углеводов."""
        if update.callback_query and update.callback_query.data == CALLBACK_MANUAL_SKIP:
            await update.callback_query.answer("⏭ Пропущено")
            return await self._show_manual_confirmation(update, context)

        try:
            carbs = float(update.message.text.strip().replace(',', '.'))
            if carbs < 0 or carbs > 1000:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Введи число от 0 до 1000 грамм.\n"
                "Например: <code>49</code>",
                parse_mode="HTML"
            )
            return STATE_MANUAL_CARBS

        context.user_data["manual_product"]["carbs"] = carbs
        return await self._show_manual_confirmation(update, context)

    async def _show_manual_confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает экран подтверждения ручного ввода."""
        product = context.user_data.get("manual_product", {})
        
        text = (
            "✅ <b>Проверь данные</b>\n\n"
            f"{format_manual_product_for_confirmation(product)}\n\n"
            "Всё верно?"
        )

        target = update.callback_query.edit_message_text if update.callback_query else update.message.reply_text
        await target(
            text,
            reply_markup=get_manual_confirm_keyboard(),
            parse_mode="HTML"
        )
        return STATE_MANUAL_CONFIRM

    async def confirm_manual_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Подтверждает ручной ввод и сохраняет продукт."""
        query = update.callback_query
        await query.answer("✓ Сохраняю...")

        product = context.user_data.get("manual_product", {})

        # Формируем calculated_food для стандартного флоу
        context.user_data["calculated_food"] = {
            "name": product["name"],
            "weight": product["weight"],
            "kcal": product["kcal"],
            "protein": product["protein"],
            "fat": product["fat"],
            "carbs": product["carbs"],
        }

        context.user_data["selected_product"] = {
            "name": product["name"],
            "code": None,  # Нет штрихкода
        }

        # Переходим к выбору типа приёма пищи
        return await self._ask_meal_type(update, context)

    async def edit_manual_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Возвращает к редактированию ручного ввода."""
        query = update.callback_query
        await query.answer()

        # Начинаем сначала
        return await self._start_manual_input(update, context)

    # ================================================================
    # УМНЫЕ ВОЗВРАТЫ
    # ================================================================

    async def _search_again(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        🎯 Магия Apple: начинает новый поиск ТЕМ ЖЕ МЕТОДОМ,
        что использовался изначально.
        """
        query = update.callback_query
        if query:
            await query.answer("🔍 Новый поиск")

        search_method = context.user_data.get("search_method", "text")
        prev_query = context.user_data.get("food_search_query", "")

        for key in [
            "search_results", "search_page", "selected_product",
            "calculated_food", "meal_type", "food_weight", "manual_product",
        ]:
            context.user_data.pop(key, None)

        if prev_query and search_method in ("text", "voice"):
            context.user_data["food_search_query"] = prev_query

        if search_method == "voice":
            return await self._start_voice_input(update, context)
        elif search_method == "popular":
            return await self._show_popular_foods(update, context)
        elif search_method == "manual":
            return await self._start_manual_input(update, context)
        elif search_method == "favorites":
            # 🎯 Если был в избранном — выходим во внешний модуль
            from handlers.favorites.handlers import FavoritesHandlers
            fav_handler = FavoritesHandlers(self.db)
            await fav_handler.show_favorites_menu(update, context)
            return ConversationHandler.END
        else:
            return await self._start_text_input(update, context)

    async def _back_to_results(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Возврат к результатам поиска с той же страницы."""
        query = update.callback_query
        if query:
            await query.answer()

        ctx = self._get_search_context(context)
        results = ctx["results"]

        if not results:
            return await self._search_again(update, context)

        start_idx = ctx["page"] * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        page_products = results[start_idx:end_idx]

        text = (
            f"🔍 <b>Результаты поиска</b>\n"
            f"Запрос: <i>«{ctx['query']}»</i>\n"
            f"Страница {ctx['page'] + 1}\n\n"
        )
        text += self._format_products_text(page_products, start_idx=start_idx)
        text += "Выбери продукт:"

        target = query.edit_message_text if query else update.message.reply_text
        await target(
            text,
            reply_markup=get_product_selection_keyboard(
                results, page=ctx["page"], query=ctx["query"]
            ),
            parse_mode="HTML"
        )

        return STATE_SELECT_PRODUCT

    async def _back_to_method(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Возврат к выбору метода."""
        return await self.show_add_food_menu(update, context)

    # ================================================================
    # ВОЗВРАТ В ДНЕВНИК
    # ================================================================

    async def _back_to_diary(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Возвращает в дневник и завершает FSM."""
        query = update.callback_query
        if query:
            await query.answer()

        for key in [
            "search_results", "search_page", "selected_product",
            "calculated_food", "meal_type", "food_weight",
            "last_added_food", "food_search_query", "search_method",
            "manual_product",
        ]:
            context.user_data.pop(key, None)

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        profile = await self.user_repo.get_profile(user_id)
        stats_repo = DailyStatsRepository(self.db)
        today_stats = await stats_repo.get_today_stats(user_id)

        from handlers.start.utils import format_diary_compact, get_main_diary_keyboard
        from handlers.water.utils import calculate_water_goal

        water_goal = calculate_water_goal(
            profile.get("weight_kg", 70),
            profile["gender"]
        )

        name = user.first_name or "друг"
        greeting = f"🥑 <b>С возвращением, {name}!</b>"

        diary_text = format_diary_compact(
            daily_kcal=profile["daily_kcal"],
            current_kcal=today_stats.get("kcal", 0),
            protein_goal=profile["daily_protein_g"],
            current_protein=today_stats.get("protein", 0),
            fat_goal=profile["daily_fat_g"],
            current_fat=today_stats.get("fat", 0),
            carbs_goal=profile["daily_carbs_g"],
            current_carbs=today_stats.get("carbs", 0),
            water_current_ml=today_stats.get("water_ml", 0),
            water_goal_ml=water_goal,
        )

        text = f"{greeting}\n\n{diary_text}"

        target = query.edit_message_text if query else update.message.reply_text
        await target(
            text,
            reply_markup=get_main_diary_keyboard(),
            parse_mode="HTML"
        )

        return ConversationHandler.END

    async def cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отмена добавления еды."""
        query = update.callback_query
        if query:
            await query.answer("❌ Отменено")
            await query.edit_message_text("❌ Добавление отменено.", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ Добавление отменено.", parse_mode="HTML")

        self._clear_search_context(context)
        return ConversationHandler.END


# ================================================================
# РЕГИСТРАЦИЯ ConversationHandler
# ================================================================

def get_add_food_conversation_handler(db: Database) -> ConversationHandler:
    """Создаёт ConversationHandler для добавления еды."""
    h = AddFoodHandlers(db)

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(h.show_add_food_menu, pattern="^food_select_method$"),
            CallbackQueryHandler(h.show_add_food_menu, pattern="^food_add_another$"),
        ],
        states={
            STATE_SELECT_METHOD: [
                CallbackQueryHandler(h.handle_method_selection, pattern="^food_method_"),
                CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            ],
            STATE_WAIT_FOR_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_text_search),
                CallbackQueryHandler(h._back_to_method, pattern=f"^{CALLBACK_BACK_TO_METHOD}$"),
                CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            ],
            STATE_SELECT_PRODUCT: [
                CallbackQueryHandler(
                    h.handle_pagination,
                    pattern=f"^({CALLBACK_PAGE_PREV}|{CALLBACK_PAGE_NEXT})$"
                ),
                CallbackQueryHandler(h.select_product, pattern=f"^{CALLBACK_SELECT_PRODUCT}"),
                CallbackQueryHandler(h._search_again, pattern=f"^{CALLBACK_SEARCH_AGAIN}$"),
                CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            ],
            STATE_ENTER_WEIGHT: [
                CallbackQueryHandler(
                    h.process_weight_selection,
                    pattern=f"^({CALLBACK_WEIGHT_PREFIX}|{CALLBACK_WEIGHT_CUSTOM}|{CALLBACK_BACK_TO_RESULTS}|{CALLBACK_SEARCH_AGAIN})"
                ),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_custom_weight),
            ],
            STATE_SELECT_MEAL_TYPE: [
                CallbackQueryHandler(
                    h.process_meal_type,
                    pattern=f"^({CALLBACK_MEAL_PREFIX}|{CALLBACK_BACK_TO_WEIGHT}|{CALLBACK_SEARCH_AGAIN})"
                ),
            ],
            STATE_CONFIRM_ADD: [
                CallbackQueryHandler(
                    h.confirm_add,
                    pattern=f"^({CALLBACK_CONFIRM_ADD}|{CALLBACK_CHANGE_WEIGHT}|{CALLBACK_SEARCH_AGAIN})$"
                ),
                CallbackQueryHandler(
                    h.handle_save_favorite,
                    pattern=f"^({CALLBACK_SAVE_FAVORITE_YES}|{CALLBACK_SAVE_FAVORITE_NO})$"
                ),
                CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            ],
            STATE_WAIT_FOR_BARCODE: [
                MessageHandler(filters.PHOTO, h.process_barcode),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_barcode),
                CallbackQueryHandler(h._back_to_method, pattern=f"^{CALLBACK_BACK_TO_METHOD}$"),
                CallbackQueryHandler(h._start_text_input, pattern=f"^{CALLBACK_BACK_TO_TEXT}$"),
                CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            ],
            STATE_AFTER_ADD: [
                CallbackQueryHandler(
                    h.handle_after_add,
                    pattern=f"^({CALLBACK_ADD_ANOTHER}|{CALLBACK_SEARCH_AGAIN}|{CALLBACK_BACK_TO_DIARY})$"
                ),
            ],
            STATE_WAIT_FOR_VOICE: [
                MessageHandler(filters.VOICE, h.process_voice_message),
                MessageHandler(filters.AUDIO, h.process_voice_message),
                CallbackQueryHandler(h._back_to_method, pattern=f"^{CALLBACK_BACK_TO_METHOD}$"),
                CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            ],
            # Ручной ввод
            STATE_MANUAL_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_manual_input),
                CallbackQueryHandler(h._back_to_method, pattern=f"^{CALLBACK_BACK_TO_METHOD}$"),
                CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            ],
            STATE_MANUAL_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_manual_name),
            ],
            STATE_MANUAL_WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_manual_weight),
                CallbackQueryHandler(h.process_manual_weight, pattern=f"^{CALLBACK_MANUAL_SKIP}$"),
            ],
            STATE_MANUAL_KCAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_manual_kcal),
            ],
            STATE_MANUAL_PROTEIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_manual_protein),
                CallbackQueryHandler(h.process_manual_protein, pattern=f"^{CALLBACK_MANUAL_SKIP}$"),
            ],
            STATE_MANUAL_FAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_manual_fat),
                CallbackQueryHandler(h.process_manual_fat, pattern=f"^{CALLBACK_MANUAL_SKIP}$"),
            ],
            STATE_MANUAL_CARBS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_manual_carbs),
                CallbackQueryHandler(h.process_manual_carbs, pattern=f"^{CALLBACK_MANUAL_SKIP}$"),
            ],
            STATE_MANUAL_CONFIRM: [
                CallbackQueryHandler(h.confirm_manual_input, pattern=f"^{CALLBACK_MANUAL_CONFIRM}$"),
                CallbackQueryHandler(h.edit_manual_input, pattern=f"^{CALLBACK_MANUAL_EDIT}$"),
                CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(h.cancel, pattern=f"^{CALLBACK_CANCEL}$"),
            CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            MessageHandler(filters.COMMAND, h.cancel),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )