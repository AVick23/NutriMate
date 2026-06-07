"""
Обработчики для добавления еды с Универсальным вводом (Apple-like UX).
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
from db.repositories import UserRepository, MealRepository, FavoritesRepository, DailyStatsRepository

from handlers.add_food.constants import (
    STATE_SELECT_METHOD, STATE_UNIVERSAL_INPUT, STATE_SELECT_PRODUCT,
    STATE_SELECT_MEAL_TYPE, STATE_CONFIRM_ADD, STATE_AFTER_ADD,
    STATE_ENTER_WEIGHT, STATE_MANUAL_CONFIRM,
    MEAL_TYPES, PAGE_SIZE,
    CALLBACK_METHOD_UNIVERSAL, CALLBACK_METHOD_FAVORITES, CALLBACK_METHOD_POPULAR,
    CALLBACK_BACK_TO_DIARY, CALLBACK_BACK_TO_RESULTS, CALLBACK_BACK_TO_WEIGHT,
    CALLBACK_SEARCH_AGAIN, CALLBACK_SELECT_PRODUCT, CALLBACK_PAGE_PREV,
    CALLBACK_PAGE_NEXT, CALLBACK_WEIGHT_PREFIX, CALLBACK_WEIGHT_CUSTOM,
    CALLBACK_MEAL_PREFIX, CALLBACK_CONFIRM_ADD, CALLBACK_CHANGE_WEIGHT,
    CALLBACK_ADD_ANOTHER, CALLBACK_SAVE_FAVORITE_YES, CALLBACK_SAVE_FAVORITE_NO,
    CALLBACK_MANUAL_CONFIRM, CALLBACK_MANUAL_EDIT, CALLBACK_CANCEL
)
from handlers.add_food.keyboards import (
    get_select_method_keyboard, get_universal_input_keyboard,
    get_meal_type_keyboard, get_product_selection_keyboard, get_weight_input_keyboard,
    get_confirm_keyboard, get_after_add_keyboard, get_save_favorite_keyboard,
    get_custom_weight_keyboard, get_manual_confirm_keyboard,
)
from handlers.add_food.api_client import OpenFoodFactsClient
from handlers.add_food.food_matcher import OptimizedFoodMatcher
from handlers.add_food.local_foods import POPULAR_FOODS
from handlers.add_food.voice_recognizer import VoiceRecognizer
from handlers.add_food.utils import parse_manual_template, format_manual_product_for_confirmation

logger = logging.getLogger(__name__)

class AddFoodHandlers:
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
        return {
            "results": context.user_data.get("search_results", []),
            "page": context.user_data.get("search_page", 0),
            "query": context.user_data.get("food_search_query", ""),
        }

    def _clear_search_context(self, context: ContextTypes.DEFAULT_TYPE):
        for key in ["search_results", "search_page", "selected_product", "calculated_food", "meal_type", "food_weight", "last_added_food", "food_search_query", "manual_product"]:
            context.user_data.pop(key, None)

    def _format_products_text(self, products: List[Dict[str, Any]], start_idx: int = 0) -> str:
        text = "─" * 17 + "\n"
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
    # 🎯 ГЛАВНОЕ МЕНЮ И УНИВЕРСАЛЬНЫЙ ВВОД
    # ================================================================
    async def show_add_food_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query:
            await query.answer()

        self._clear_search_context(context)

        text = "🍽️ <b>Добавление еды</b>\n\nВыбери действие:"
        target = query.edit_message_text if query else update.message.reply_text
        await target(text, reply_markup=get_select_method_keyboard(), parse_mode="HTML")
        return STATE_SELECT_METHOD

    async def handle_method_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        method = query.data

        if method == CALLBACK_METHOD_UNIVERSAL:
            return await self._start_universal_input(update, context)
        elif method == CALLBACK_METHOD_FAVORITES:
            self._clear_search_context(context)
            from handlers.favorites.handlers import FavoritesHandlers
            fav_handler = FavoritesHandlers(self.db)
            await fav_handler.show_favorites_menu(update, context)
            return ConversationHandler.END
        elif method == CALLBACK_METHOD_POPULAR:
            return await self._show_popular_foods(update, context)
        elif method == CALLBACK_BACK_TO_DIARY:
            return await self._back_to_diary(update, context)

        return STATE_SELECT_METHOD

    async def _start_universal_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query:
            await query.answer()

        text = (
            "🍽️ <b>Что ты съел?</b>\n\n"
            "Просто отправь мне одним сообщением:\n"
            "🎤 Голосовое сообщение\n"
            "📷 Фото штрихкода или упаковки\n"
            "✍️ Название (например, «гречка с котлетой 300г»)\n"
            "📋 Или данные по шаблону (Название 300г 500ккал Б20 Ж10 У50)\n\n"
            "<i>Я сам пойму формат и всё посчитаю! 🧠</i>"
        )
        target = query.edit_message_text if query else update.message.reply_text
        await target(text, reply_markup=get_universal_input_keyboard(), parse_mode="HTML")
        return STATE_UNIVERSAL_INPUT

    async def process_universal_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """🎯 МАГИЯ: Один обработчик для текста, фото и голоса."""
        message = update.message
        if not message:
            return STATE_UNIVERSAL_INPUT

        # 1. 🎤 ГОЛОС
        if message.voice or message.audio:
            return await self._handle_universal_voice(update, context)
        
        # 2. 📷 ФОТО (Штрихкод)
        elif message.photo:
            return await self._handle_universal_photo(update, context)
        
        # 3. ✍️ ТЕКСТ
        elif message.text:
            text = message.text.strip()
            
            # 3.1. Проверяем, не является ли это продвинутым шаблоном ручного ввода
            parsed_manual = parse_manual_template(text)
            if parsed_manual:
                context.user_data["manual_product"] = parsed_manual
                return await self._show_manual_confirmation(update, context)
            
            # 3.2. Иначе это обычный текстовый поиск
            return await self._handle_universal_text(update, context, text)
        
        # 4. ❌ НЕПОДХОДЯЩИЙ ФОРМАТ
        else:
            await message.reply_text(
                "🤔 Я пока не умею это распознавать.\n\n"
                "Пожалуйста, отправь: голосовое, фото штрихкода или текстовое название.",
                reply_markup=get_universal_input_keyboard()
            )
            return STATE_UNIVERSAL_INPUT

    # ================================================================
    # ВНУТРЕННИЕ ОБРАБОТЧИКИ УНИВЕРСАЛЬНОГО ВВОДА
    # ================================================================
    async def _handle_universal_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        status_msg = await update.message.reply_text("👂 <b>Слушаю...</b>\n\nРаспознаю твоё голосовое сообщение...", parse_mode="HTML")
        recognized_text = await self.voice_recognizer.recognize(update, context)

        if not recognized_text:
            await status_msg.edit_text("❌ <b>Не удалось распознать</b>\n\nПопробуй ещё раз или напиши текстом.", reply_markup=get_universal_input_keyboard(), parse_mode="HTML")
            return STATE_UNIVERSAL_INPUT

        await status_msg.edit_text(f"🎤 <b>Я услышал:</b>\n<i>«{recognized_text}»</i>\n\n🔍 Ищу продукты...", parse_mode="HTML")
        
        food_name, weight, unit = self.food_matcher.parse_quantity_from_text(recognized_text)
        context.user_data["food_search_query"] = food_name
        if weight and (not unit or unit == 'г'):
            context.user_data["food_weight"] = weight

        return await self._execute_search_and_show_results(update, context, food_name, status_msg)

    async def _handle_universal_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        status_msg = await update.message.reply_text("📷 <b>Сканирую штрихкод...</b>", parse_mode="HTML")
        barcode = await self._decode_barcode_from_photo(update, context)

        if not barcode:
            await status_msg.edit_text(
                "❌ Не удалось распознать штрихкод.\n\n"
                "Попробуй:\n• Сделать фото крупным планом\n• Улучшить освещение\n• Или просто напиши название текстом",
                reply_markup=get_universal_input_keyboard(), parse_mode="HTML"
            )
            return STATE_UNIVERSAL_INPUT

        await status_msg.edit_text(f"✅ Штрихкод: <code>{barcode}</code>\n\n🔍 Ищу продукт в базе...", parse_mode="HTML")
        product = await self.api_client.get_product_by_barcode(barcode)

        if not product:
            await status_msg.edit_text(
                f"❌ Продукт со штрихкодом <code>{barcode}</code> не найден в базе.\n\nПопробуй найти через текстовый поиск.",
                reply_markup=get_universal_input_keyboard(), parse_mode="HTML"
            )
            return STATE_UNIVERSAL_INPUT

        context.user_data["selected_product"] = product
        context.user_data["search_results"] = [product]
        context.user_data["search_page"] = 0
        await status_msg.delete()
        
        text = f"✅ <b>Продукт найден!</b>\n\n🍽 <b>{product['name']}</b>\n🔥 {product.get('kcal_100g', 0):.0f} ккал / 100г\n\nСколько грамм ты съел?"
        await update.message.reply_text(text, reply_markup=get_weight_input_keyboard(product['name']), parse_mode="HTML")
        return STATE_ENTER_WEIGHT

    async def _handle_universal_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> int:
        food_name, weight, unit = self.food_matcher.parse_quantity_from_text(text)
        if unit and unit != 'г':
            weight = None

        context.user_data["food_search_query"] = food_name
        if weight:
            context.user_data["food_weight"] = weight

        status_msg = await update.message.reply_text("🔍 <b>Ищу продукты...</b>", parse_mode="HTML")
        return await self._execute_search_and_show_results(update, context, food_name, status_msg)

    async def _execute_search_and_show_results(self, update: Update, context: ContextTypes.DEFAULT_TYPE, food_name: str, status_msg) -> int:
        products = await self.food_matcher.search_with_api_fallback(food_name)

        if not products:
            await status_msg.edit_text(
                f"❌ По запросу <i>«{food_name}»</i> ничего не найдено.\n\nПопробуй написать по-другому или проверить опечатки.",
                reply_markup=get_universal_input_keyboard(), parse_mode="HTML"
            )
            return STATE_UNIVERSAL_INPUT

        context.user_data["search_results"] = products
        context.user_data["search_page"] = 0
        total = len(products)
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

        text = f"🔍 <b>Найдено: {total} продуктов</b>\nЗапрос: <i>«{food_name}»</i>\nСтраница 1 из {pages}\n\n"
        text += self._format_products_text(products[:PAGE_SIZE], start_idx=0)
        text += "Выбери подходящий вариант:"

        await status_msg.delete()
        await update.message.reply_text(text, reply_markup=get_product_selection_keyboard(products, page=0, query=food_name), parse_mode="HTML")
        return STATE_SELECT_PRODUCT

    # ================================================================
    # ПОПУЛЯРНЫЕ БЛЮДА
    # ================================================================
    async def _show_popular_foods(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        context.user_data["search_results"] = POPULAR_FOODS
        context.user_data["search_page"] = 0
        context.user_data["food_search_query"] = "Популярные блюда"

        total = len(POPULAR_FOODS)
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        text = f"🔥 <b>Популярные блюда</b>\n\nВсего: {total} блюд\nСтраница 1 из {pages}\n\n"
        text += self._format_products_text(POPULAR_FOODS[:PAGE_SIZE], start_idx=0)
        text += "Выбери блюдо из списка:"

        await query.edit_message_text(text, reply_markup=get_product_selection_keyboard(POPULAR_FOODS, page=0, query="Популярные блюда"), parse_mode="HTML")
        return STATE_SELECT_PRODUCT

    # ================================================================
    # ВЫБОР ПРОДУКТА И ПАГИНАЦИЯ
    # ================================================================
    async def select_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    async def handle_pagination(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

        text = f"🔍 <b>Найдено: {len(results)} продуктов</b>\nЗапрос: <i>«{ctx['query']}»</i>\nСтраница {new_page + 1} из {total_pages}\n\n"
        text += self._format_products_text(page_products, start_idx=start_idx)
        text += "Выбери подходящий вариант:"

        await query.edit_message_text(text, reply_markup=get_product_selection_keyboard(results, page=new_page, query=ctx["query"]), parse_mode="HTML")
        return STATE_SELECT_PRODUCT

    # ================================================================
    # ВЫБОР ВЕСА
    # ================================================================
    async def _ask_weight(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query:
            await query.answer()
        product = context.user_data.get("selected_product", {})
        default_weight = product.get("default_weight", 100)
        name = product.get("name", "")[:40]

        text = f"⚖️ <b>Сколько грамм?</b>\n\n🍽 <b>{name}</b>\n💡 Обычно: ~{default_weight:.0f}г\n\nВыбери из вариантов или введи свой."
        target = query.edit_message_text if query else update.message.reply_text
        await target(text, reply_markup=get_weight_input_keyboard(name), parse_mode="HTML")
        return STATE_ENTER_WEIGHT

    async def process_weight_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == CALLBACK_BACK_TO_RESULTS:
            return await self._back_to_results(update, context)
        if data == CALLBACK_SEARCH_AGAIN:
            return await self._search_again(update, context)
        if data == CALLBACK_WEIGHT_CUSTOM:
            await query.edit_message_text("✏️ <b>Введи вес в граммах</b>\n\nТолько число, например: <code>150</code>", reply_markup=get_custom_weight_keyboard(), parse_mode="HTML")
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

    async def process_custom_weight(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_input = update.message.text.strip()
        try:
            weight = float(user_input.replace(",", "."))
            if weight <= 0 or weight > 10000:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Введи число от 1 до 10000 грамм.\nНапример: <code>150</code>", reply_markup=get_custom_weight_keyboard(), parse_mode="HTML")
            return STATE_ENTER_WEIGHT

        product = context.user_data.get("selected_product", {})
        calculated = self.api_client.calculate_for_weight(product, weight)
        context.user_data["calculated_food"] = calculated
        await self._ask_meal_type_message(update, context)
        return STATE_SELECT_MEAL_TYPE

    # ================================================================
    # ТИП ПРИЁМА ПИЩИ
    # ================================================================
    async def _ask_meal_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query:
            await query.answer()
        calculated = context.user_data.get("calculated_food", {})
        text = self._format_meal_type_text(calculated)
        target = query.edit_message_text if query else update.message.reply_text
        await target(text, reply_markup=get_meal_type_keyboard(), parse_mode="HTML")
        return STATE_SELECT_MEAL_TYPE

    async def _ask_meal_type_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        calculated = context.user_data.get("calculated_food", {})
        text = self._format_meal_type_text(calculated)
        await update.message.reply_text(text, reply_markup=get_meal_type_keyboard(), parse_mode="HTML")

    def _format_meal_type_text(self, calculated: dict) -> str:
        return (
            f"🍽️ <b>Когда ты это съел?</b>\n\n"
            f"🍳 <b>{calculated.get('name', '')}</b>\n"
            f"⚖️ {calculated.get('weight', 0):.0f}г\n\n"
            f"🔥 {calculated.get('kcal', 0)} ккал · "
            f"🍗 {calculated.get('protein', 0):.1f}г · "
            f"🥑 {calculated.get('fat', 0):.1f}г · "
            f"🍚 {calculated.get('carbs', 0):.1f}г"
        )

    async def process_meal_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        await query.edit_message_text(text, reply_markup=get_confirm_keyboard(), parse_mode="HTML")
        return STATE_CONFIRM_ADD

    # ================================================================
    # ПОДТВЕРЖДЕНИЕ И СОХРАНЕНИЕ
    # ================================================================
    async def confirm_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
            user_id=user_id, meal_type=meal_type, food_name=calculated["name"],
            amount_g=calculated["weight"], kcal=calculated["kcal"],
            protein_g=calculated["protein"], fat_g=calculated["fat"],
            carbs_g=calculated["carbs"], barcode=selected.get("code")
        )

        meal_label = MEAL_TYPES.get(meal_type, meal_type)
        context.user_data["last_added_food"] = {
            "name": calculated["name"], "amount_g": calculated["weight"], "kcal": calculated["kcal"],
            "protein_g": calculated["protein"], "fat_g": calculated["fat"], "carbs_g": calculated["carbs"],
            "barcode": selected.get("code"),
        }

        text = f"✅ <b>Добавлено в {meal_label}!</b>\n\n🍳 <b>{calculated['name']}</b>\n⚖️ {calculated['weight']:.0f}г\n🔥 {calculated['kcal']} ккал\n\nСохранить в избранное?"
        await query.edit_message_text(text, reply_markup=get_save_favorite_keyboard(), parse_mode="HTML")
        return STATE_CONFIRM_ADD

    async def handle_save_favorite(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        food_data = context.user_data.get("last_added_food", {})

        if data == CALLBACK_SAVE_FAVORITE_YES and food_data:
            await self.favorites_repo.add_favorite(
                user_id=user_id, food_name=food_data["name"], amount_g=food_data["amount_g"],
                kcal=food_data["kcal"], protein_g=food_data["protein_g"], fat_g=food_data["fat_g"],
                carbs_g=food_data["carbs_g"], barcode=food_data.get("barcode")
            )
            await query.answer("⭐ Сохранено в избранное!", show_alert=False)

        last_food = context.user_data.get("last_added_food", {})
        text = f"🎉 <b>Готово!</b>\n\n🍳 {last_food.get('name', 'Блюдо')} добавлено.\n\nЧто хочешь сделать?"
        await query.edit_message_text(text, reply_markup=get_after_add_keyboard(), parse_mode="HTML")
        return STATE_AFTER_ADD

    async def handle_after_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    # РУЧНОЙ ВВОД (FALLBACK)
    # ================================================================
    async def _show_manual_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        product = context.user_data.get("manual_product", {})
        text = "✅ <b>Проверь данные</b>\n\n" + format_manual_product_for_confirmation(product) + "\n\nВсё верно?"
        target = update.callback_query.edit_message_text if update.callback_query else update.message.reply_text
        await target(text, reply_markup=get_manual_confirm_keyboard(), parse_mode="HTML")
        return STATE_MANUAL_CONFIRM

    async def confirm_manual_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer("✓ Сохраняю...")
        product = context.user_data.get("manual_product", {})
        context.user_data["calculated_food"] = {
            "name": product["name"], "weight": product["weight"], "kcal": product["kcal"],
            "protein": product["protein"], "fat": product["fat"], "carbs": product["carbs"],
        }
        context.user_data["selected_product"] = {"name": product["name"], "code": None}
        return await self._ask_meal_type(update, context)

    async def edit_manual_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        return await self._start_universal_input(update, context)

    # ================================================================
    # УМНЫЕ ВОЗВРАТЫ И ОТМЕНА
    # ================================================================
    async def _search_again(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query:
            await query.answer("🔍 Новый поиск")
        
        self._clear_search_context(context)
        return await self._start_universal_input(update, context)

    async def _back_to_results(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

        text = f"🔍 <b>Результаты поиска</b>\nЗапрос: <i>«{ctx['query']}»</i>\nСтраница {ctx['page'] + 1}\n\n"
        text += self._format_products_text(page_products, start_idx=start_idx)
        text += "Выбери продукт:"

        target = query.edit_message_text if query else update.message.reply_text
        await target(text, reply_markup=get_product_selection_keyboard(results, page=ctx["page"], query=ctx["query"]), parse_mode="HTML")
        return STATE_SELECT_PRODUCT

    async def _back_to_diary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query:
            await query.answer()
        self._clear_search_context(context)

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        profile = await self.user_repo.get_profile(user_id)
        stats_repo = DailyStatsRepository(self.db)
        today_stats = await stats_repo.get_today_stats(user_id)

        from handlers.start.utils import format_diary_compact, get_main_diary_keyboard
        from handlers.water.utils import calculate_water_goal

        water_goal = calculate_water_goal(profile.get("weight_kg", 70), profile["gender"])
        name = user.first_name or "друг"
        greeting = f"🥑 <b>С возвращением, {name}!</b>"
        diary_text = format_diary_compact(
            daily_kcal=profile["daily_kcal"], current_kcal=today_stats.get("kcal", 0),
            protein_goal=profile["daily_protein_g"], current_protein=today_stats.get("protein", 0),
            fat_goal=profile["daily_fat_g"], current_fat=today_stats.get("fat", 0),
            carbs_goal=profile["daily_carbs_g"], current_carbs=today_stats.get("carbs", 0),
            water_current_ml=today_stats.get("water_ml", 0), water_goal_ml=water_goal,
        )
        text = f"{greeting}\n\n{diary_text}"
        target = query.edit_message_text if query else update.message.reply_text
        await target(text, reply_markup=get_main_diary_keyboard(), parse_mode="HTML")
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query:
            await query.answer("❌ Отменено")
            await query.edit_message_text("❌ Добавление отменено.", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ Добавление отменено.", parse_mode="HTML")
        self._clear_search_context(context)
        return ConversationHandler.END

    # ================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ДЛЯ ШТРИХКОДА
    # ================================================================
    async def _decode_barcode_from_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
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
        variants = [image]
        try:
            gray = image.convert('L')
            enhanced = ImageEnhance.Contrast(gray).enhance(2.0)
            enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.5)
            variants.append(enhanced)
        except Exception: pass
        try:
            gray = image.convert('L')
            variants.append(gray.filter(ImageFilter.SHARPEN))
        except Exception: pass
        for angle in [90, 180, 270]:
            try:
                variants.append(image.rotate(angle, expand=True))
            except Exception: continue
        return variants

    def _validate_barcode(self, barcode: str) -> bool:
        if not barcode.isdigit(): return False
        if len(barcode) not in [8, 12, 13, 14]: return False
        if len(barcode) == 13: return self._verify_ean13_checksum(barcode)
        return True

    def _verify_ean13_checksum(self, barcode: str) -> bool:
        try:
            digits = [int(d) for d in barcode]
            weighted_sum = sum(digits[i] * (1 if i % 2 == 0 else 3) for i in range(12))
            check_digit = (10 - (weighted_sum % 10)) % 10
            return check_digit == digits[12]
        except Exception:
            return False


# ================================================================
# РЕГИСТРАЦИЯ ConversationHandler
# ================================================================
def get_add_food_conversation_handler(db: Database) -> ConversationHandler:
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
            # 🎯 ЕДИНЫЙ ОБРАБОТЧИК ДЛЯ ВСЕХ ТИПОВ ВВОДА
            STATE_UNIVERSAL_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_universal_input),
                MessageHandler(filters.VOICE | filters.AUDIO, h.process_universal_input),
                MessageHandler(filters.PHOTO, h.process_universal_input),
                CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            ],
            STATE_SELECT_PRODUCT: [
                CallbackQueryHandler(h.handle_pagination, pattern=f"^({CALLBACK_PAGE_PREV}|{CALLBACK_PAGE_NEXT})$"),
                CallbackQueryHandler(h.select_product, pattern=f"^{CALLBACK_SELECT_PRODUCT}"),
                CallbackQueryHandler(h._search_again, pattern=f"^{CALLBACK_SEARCH_AGAIN}$"),
                CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            ],
            STATE_ENTER_WEIGHT: [
                CallbackQueryHandler(h.process_weight_selection, pattern=f"^({CALLBACK_WEIGHT_PREFIX}|{CALLBACK_WEIGHT_CUSTOM}|{CALLBACK_BACK_TO_RESULTS}|{CALLBACK_SEARCH_AGAIN})"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_custom_weight),
            ],
            STATE_SELECT_MEAL_TYPE: [
                CallbackQueryHandler(h.process_meal_type, pattern=f"^({CALLBACK_MEAL_PREFIX}|{CALLBACK_BACK_TO_WEIGHT}|{CALLBACK_SEARCH_AGAIN})"),
            ],
            STATE_CONFIRM_ADD: [
                CallbackQueryHandler(h.confirm_add, pattern=f"^({CALLBACK_CONFIRM_ADD}|{CALLBACK_CHANGE_WEIGHT}|{CALLBACK_SEARCH_AGAIN})$"),
                CallbackQueryHandler(h.handle_save_favorite, pattern=f"^({CALLBACK_SAVE_FAVORITE_YES}|{CALLBACK_SAVE_FAVORITE_NO})$"),
                CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            ],
            STATE_AFTER_ADD: [
                CallbackQueryHandler(h.handle_after_add, pattern=f"^({CALLBACK_ADD_ANOTHER}|{CALLBACK_SEARCH_AGAIN}|{CALLBACK_BACK_TO_DIARY})$"),
            ],
            # Fallback для ручного ввода
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