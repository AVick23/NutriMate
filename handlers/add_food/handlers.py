# handlers/add_food/handlers.py
import io
import logging
from typing import Optional

from PIL import Image
from pyzbar.pyzbar import decode
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters
)

from db.database import Database
from db.models import UserRepository, MealRepository, FavoritesRepository, DailyStatsRepository
from handlers.add_food.constants import (
    STATE_SELECT_METHOD, STATE_WAIT_FOR_TEXT, STATE_SELECT_PRODUCT,
    STATE_SELECT_MEAL_TYPE, STATE_ENTER_WEIGHT, STATE_CONFIRM_ADD,
    STATE_WAIT_FOR_BARCODE, STATE_SELECT_FAVORITE, MEAL_TYPES
)
from handlers.add_food.keyboards import (
    get_select_method_keyboard, get_back_keyboard, get_barcode_back_keyboard,
    get_meal_type_keyboard, get_product_selection_keyboard, get_weight_input_keyboard,
    get_confirm_keyboard, get_after_add_keyboard, get_save_favorite_keyboard,
    get_favorites_keyboard, get_custom_weight_keyboard
)
from handlers.add_food.api_client import OpenFoodFactsClient
from handlers.add_food.utils import parse_food_text
from handlers.add_food.food_matcher import OptimizedFoodMatcher
from handlers.add_food.local_foods import POPULAR_FOODS

logger = logging.getLogger(__name__)


class AddFoodHandlers:
    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.meal_repo = MealRepository(db)
        self.favorites_repo = FavoritesRepository(db)
        self.api_client = OpenFoodFactsClient()
        self.food_matcher = OptimizedFoodMatcher(POPULAR_FOODS, self.api_client)

    # ========== Входная точка ==========

    async def show_add_food_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает меню выбора способа добавления еды."""
        query = update.callback_query
        await query.answer()

        text = (
            "🍽️ <b>Добавление еды</b>\n\n"
            "Выбери, как удобнее записать приём пищи."
        )

        await query.edit_message_text(
            text,
            reply_markup=get_select_method_keyboard(),
            parse_mode="HTML"
        )
        return STATE_SELECT_METHOD

    async def handle_method_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор способа добавления."""
        query = update.callback_query
        await query.answer()

        method = query.data

        if method == "food_method_text":
            return await self._start_text_input(update, context)
        elif method == "food_method_barcode":
            return await self._start_barcode_scan(update, context)
        elif method == "food_method_favorites":
            return await self._show_favorites(update, context)
        elif method == "food_method_popular":
            return await self._show_popular_foods(update, context)
        elif method == "food_method_photo":
            await query.edit_message_text(
                "📸 Функция распознавания по фото пока в разработке.\n"
                "Пожалуйста, выбери другой способ.",
                reply_markup=get_back_keyboard("food_back_to_diary"),
                parse_mode="HTML"
            )
            return STATE_SELECT_METHOD
        elif method == "food_back_to_diary":
            return await self._back_to_diary(update, context)

        return STATE_SELECT_METHOD

    # ========== Популярные блюда ==========

    async def _show_popular_foods(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает список популярных блюд из локальной базы."""
        query = update.callback_query
        await query.answer()

        popular = POPULAR_FOODS[:10]
        context.user_data["search_results"] = popular

        text = "🔥 <b>Популярные блюда</b>\n\n"
        text += "─" * 17 + "\n"

        for i, product in enumerate(popular):
            name = product["name"][:40]
            brand = f" ({product.get('brand', '')})" if product.get("brand") else ""
            kcal = product.get("kcal_100g", 0)
            protein = product.get("protein_100g", 0)
            fat = product.get("fat_100g", 0)
            carbs = product.get("carbs_100g", 0)
            weight_def = product.get("default_weight", 100)

            text += f"<b>{i + 1}.</b> {name}{brand}\n"
            text += f"Вес порции: ~{weight_def:.0f} г\n"
            text += f"🔥 {kcal:.0f} ккал | 🍗 {protein:.1f}г | 🥑 {fat:.1f}г | 🍚 {carbs:.1f}г\n\n"

        text += "─" * 17 + "\n"
        text += "Выбери блюдо из списка."

        await query.edit_message_text(
            text,
            reply_markup=get_product_selection_keyboard(popular),
            parse_mode="HTML"
        )
        return STATE_SELECT_PRODUCT

    # ========== Текстовый поиск ==========

    async def _start_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начинает ввод текста для поиска."""
        query = update.callback_query

        text = (
            "✍️ <b>Опиши, что ты съел</b>\n\n"
            "Напиши в ответ одним сообщением название блюда или продукта. "
            "Если знаешь вес — укажи его в граммах.\n\n"
            "<b>Примеры:</b>\n"
            "• <code>гречка с котлетой 300г</code>\n"
            "• <code>омлет из двух яиц с сыром</code>\n"
            "• <code>банан</code>\n\n"
            "Я сам найду калорийность и предложу варианты."
        )

        await query.edit_message_text(
            text,
            reply_markup=get_back_keyboard("food_back_to_diary"),
            parse_mode="HTML"
        )
        return STATE_WAIT_FOR_TEXT

    async def process_text_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает текстовый запрос с предобработкой и API V3."""
        user_input = update.message.text.strip()
        
        # Используем улучшенный парсер из food_matcher
        food_name, weight, unit = self.food_matcher.parse_quantity_from_text(user_input)
        
        # Если единица измерения не 'г', преобразуем или игнорируем
        if unit and unit != 'г':
            # Для штук и мл пока не делаем автоматический пересчёт
            weight = None
        
        context.user_data["food_search_query"] = food_name
        if weight:
            context.user_data["food_weight"] = weight

        status_msg = await update.message.reply_text("🔍 Ищу продукты...")
        
        # Поиск с предобработкой (API V3 → fallback)
        products = await self.food_matcher.search_with_api_fallback(food_name)

        if not products:
            await status_msg.edit_text(
                f"❌ По запросу <i>«{food_name}»</i> ничего не найдено.\n"
                "Попробуй написать по-другому или проверь опечатки.",
                reply_markup=get_back_keyboard("food_back_to_diary"),
                parse_mode="HTML"
            )
            return STATE_WAIT_FOR_TEXT

        context.user_data["search_results"] = products

        text = f"🔍 <b>Вот что я нашёл по запросу:</b>\n<i>«{food_name}»</i>\n\n"
        text += "─" * 17 + "\n"

        for i, product in enumerate(products[:5]):
            name = product["name"][:40]
            brand = f" ({product.get('brand', '')})" if product.get("brand") else ""
            kcal = product.get("kcal_100g", 0)
            protein = product.get("protein_100g", 0)
            fat = product.get("fat_100g", 0)
            carbs = product.get("carbs_100g", 0)

            text += f"<b>{i + 1}.</b> {name}{brand}\n"
            text += f"🔥 {kcal:.0f} ккал | 🍗 {protein:.1f}г | 🥑 {fat:.1f}г | 🍚 {carbs:.1f}г\n\n"

        text += "─" * 17 + "\n"
        text += "Выбери подходящий вариант."

        await status_msg.delete()
        await update.message.reply_text(
            text,
            reply_markup=get_product_selection_keyboard(products),
            parse_mode="HTML"
        )

        return STATE_SELECT_PRODUCT

    async def select_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор продукта из результатов."""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == "food_back_to_diary":
            return await self._back_to_diary(update, context)

        try:
            index = int(data.replace("food_product_", ""))
        except ValueError:
            return STATE_SELECT_PRODUCT

        products = context.user_data.get("search_results", [])
        if index >= len(products):
            await query.answer("Продукт не найден")
            return STATE_SELECT_PRODUCT

        selected_product = products[index]
        context.user_data["selected_product"] = selected_product

        if "food_weight" in context.user_data:
            weight = context.user_data["food_weight"]
            calculated = self.api_client.calculate_for_weight(selected_product, weight)
            context.user_data["calculated_food"] = calculated
            return await self._ask_meal_type(update, context)
        else:
            return await self._ask_weight(update, context)

    # ========== Выбор веса ==========

    async def _ask_weight(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Спрашивает вес продукта."""
        query = update.callback_query
        product = context.user_data.get("selected_product", {})
        default_weight = product.get("default_weight", 100)

        text = (
            f"⚖️ <b>Укажи вес порции</b>\n\n"
            f"<b>{product.get('name', '')}</b>\n"
            f"Вес по умолчанию: {default_weight:.0f} г\n\n"
            f"Выбери из вариантов или введи свой."
        )

        await query.edit_message_text(
            text,
            reply_markup=get_weight_input_keyboard(),
            parse_mode="HTML"
        )
        return STATE_ENTER_WEIGHT

    async def process_weight_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор веса."""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == "food_back_to_products":
            products = context.user_data.get("search_results", [])
            await query.edit_message_text(
                "Выбери продукт:",
                reply_markup=get_product_selection_keyboard(products),
                parse_mode="HTML"
            )
            return STATE_SELECT_PRODUCT

        elif data == "food_weight_custom":
            await query.edit_message_text(
                "✏️ Введи вес в граммах (только число):\n"
                "Например: <code>150</code>",
                reply_markup=get_custom_weight_keyboard(),
                parse_mode="HTML"
            )
            return STATE_ENTER_WEIGHT

        elif data.startswith("food_weight_"):
            try:
                weight = float(data.replace("food_weight_", ""))
            except ValueError:
                return STATE_ENTER_WEIGHT

            product = context.user_data.get("selected_product", {})
            calculated = self.api_client.calculate_for_weight(product, weight)
            context.user_data["calculated_food"] = calculated
            return await self._ask_meal_type(update, context)

        return STATE_ENTER_WEIGHT

    async def process_custom_weight(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает ввод своего веса."""
        user_input = update.message.text.strip()

        try:
            weight = float(user_input)
            if weight <= 0 or weight > 10000:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Введи положительное число (в граммах).\n"
                "Например: <code>150</code>",
                parse_mode="HTML"
            )
            return STATE_ENTER_WEIGHT

        product = context.user_data.get("selected_product", {})
        calculated = self.api_client.calculate_for_weight(product, weight)
        context.user_data["calculated_food"] = calculated

        await self._ask_meal_type_message(update, context)
        return STATE_SELECT_MEAL_TYPE

    # ========== Выбор типа приёма пищи ==========

    async def _ask_meal_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Спрашивает тип приёма пищи (callback)."""
        query = update.callback_query
        calculated = context.user_data.get("calculated_food", {})

        text = (
            f"🍽️ <b>Когда ты это съел?</b>\n\n"
            f"<b>{calculated.get('name', '')}</b>\n"
            f"Вес: {calculated.get('weight', 0):.0f} г\n"
            f"🔥 {calculated.get('kcal', 0)} ккал | "
            f"🍗 {calculated.get('protein', 0):.1f}г | "
            f"🥑 {calculated.get('fat', 0):.1f}г | "
            f"🍚 {calculated.get('carbs', 0):.1f}г\n\n"
            f"Выбери тип приёма пищи:"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_meal_type_keyboard(),
            parse_mode="HTML"
        )
        return STATE_SELECT_MEAL_TYPE

    async def _ask_meal_type_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Спрашивает тип приёма пищи (message)."""
        calculated = context.user_data.get("calculated_food", {})

        text = (
            f"🍽️ <b>Когда ты это съел?</b>\n\n"
            f"<b>{calculated.get('name', '')}</b>\n"
            f"Вес: {calculated.get('weight', 0):.0f} г\n"
            f"🔥 {calculated.get('kcal', 0)} ккал | "
            f"🍗 {calculated.get('protein', 0):.1f}г | "
            f"🥑 {calculated.get('fat', 0):.1f}г | "
            f"🍚 {calculated.get('carbs', 0):.1f}г\n\n"
            f"Выбери тип приёма пищи:"
        )

        await update.message.reply_text(
            text,
            reply_markup=get_meal_type_keyboard(),
            parse_mode="HTML"
        )

    async def process_meal_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор типа приёма пищи."""
        query = update.callback_query
        await query.answer()

        meal_type = query.data.replace("food_meal_", "")
        context.user_data["meal_type"] = meal_type

        calculated = context.user_data.get("calculated_food", {})
        meal_label = MEAL_TYPES.get(meal_type, meal_type)

        text = (
            f"✅ <b>Подтверждение</b>\n\n"
            f"<b>{calculated.get('name', '')}</b>\n"
            f"Вес: {calculated.get('weight', 0):.0f} г\n"
            f"Приём пищи: {meal_label}\n\n"
            f"🔥 {calculated.get('kcal', 0)} ккал | "
            f"🍗 {calculated.get('protein', 0):.1f}г | "
            f"🥑 {calculated.get('fat', 0):.1f}г | "
            f"🍚 {calculated.get('carbs', 0):.1f}г\n\n"
            f"Всё верно?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_confirm_keyboard(),
            parse_mode="HTML"
        )
        return STATE_CONFIRM_ADD

    # ========== Подтверждение и сохранение ==========

    async def confirm_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Подтверждает добавление и сохраняет в БД."""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == "food_change_weight":
            return await self._ask_weight(update, context)

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)

        calculated = context.user_data.get("calculated_food", {})
        meal_type = context.user_data.get("meal_type", "snack")
        selected_product = context.user_data.get("selected_product", {})

        await self.meal_repo.add_meal(
            user_id=user_id,
            meal_type=meal_type,
            food_name=calculated["name"],
            amount_g=calculated["weight"],
            kcal=calculated["kcal"],
            protein_g=calculated["protein"],
            fat_g=calculated["fat"],
            carbs_g=calculated["carbs"],
            barcode=selected_product.get("code")
        )

        # Очищаем временные данные
        for key in ["search_results", "selected_product", "calculated_food", "meal_type", "food_weight"]:
            context.user_data.pop(key, None)

        meal_label = MEAL_TYPES.get(meal_type, meal_type)

        text = (
            f"✅ <b>Добавлено в {meal_label}!</b>\n\n"
            f"🍳 <b>{calculated['name']}</b>\n"
            f"🔥 {calculated['kcal']} ккал | "
            f"🍗 {calculated['protein']:.1f}г | "
            f"🥑 {calculated['fat']:.1f}г | "
            f"🍚 {calculated['carbs']:.1f}г\n\n"
            f"─────────────────\n\n"
            f"Хочешь сохранить это блюдо в избранное?"
        )

        context.user_data["last_added_food"] = {
            "name": calculated["name"],
            "amount_g": calculated["weight"],
            "kcal": calculated["kcal"],
            "protein_g": calculated["protein"],
            "fat_g": calculated["fat"],
            "carbs_g": calculated["carbs"],
            "barcode": selected_product.get("code")
        }

        await query.edit_message_text(
            text,
            reply_markup=get_save_favorite_keyboard(),
            parse_mode="HTML"
        )
        return STATE_CONFIRM_ADD

    async def handle_save_favorite(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает сохранение в избранное."""
        query = update.callback_query
        await query.answer()

        data = query.data
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)

        food_data = context.user_data.get("last_added_food", {})

        if data == "food_save_favorite_yes" and food_data:
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

        # Очищаем последнее добавленное блюдо
        context.user_data.pop("last_added_food", None)

        text = (
            f"✅ <b>Блюдо добавлено!</b>\n\n"
            f"Что хочешь сделать дальше?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_after_add_keyboard(),
            parse_mode="HTML"
        )
        return STATE_CONFIRM_ADD

    # ========== Штрихкод ==========

    async def _start_barcode_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начинает сканирование штрихкода."""
        query = update.callback_query

        text = (
            "📷 <b>Сканирование штрихкода</b>\n\n"
            "Отправь мне <b>фото штрихкода</b> или просто напиши цифры с упаковки."
        )

        await query.edit_message_text(
            text,
            reply_markup=get_barcode_back_keyboard(),
            parse_mode="HTML"
        )
        return STATE_WAIT_FOR_BARCODE

    async def process_barcode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает полученный штрихкод."""
        if update.message.photo:
            status_msg = await update.message.reply_text("🔍 Распознаю штрихкод...")
            barcode = await self._decode_barcode_from_photo(update, context)

            if not barcode:
                await status_msg.edit_text(
                    "❌ Не удалось распознать штрихкод.\n"
                    "Попробуй ещё раз или введи цифры вручную.",
                    reply_markup=get_barcode_back_keyboard(),
                    parse_mode="HTML"
                )
                return STATE_WAIT_FOR_BARCODE

            await status_msg.edit_text(f"✅ Штрихкод: <code>{barcode}</code>", parse_mode="HTML")
        else:
            barcode = update.message.text.strip()
            if not barcode.isdigit() or len(barcode) < 8:
                await update.message.reply_text(
                    "❌ Это не похоже на штрихкод.",
                    parse_mode="HTML"
                )
                return STATE_WAIT_FOR_BARCODE

        status_msg = await update.message.reply_text("🔍 Ищу продукт в базе...")
        product = await self.api_client.get_product_by_barcode(barcode)

        if not product:
            await status_msg.edit_text(
                f"❌ Продукт не найден.\n"
                "Попробуй найти вручную через текстовый поиск.",
                reply_markup=get_barcode_back_keyboard(),
                parse_mode="HTML"
            )
            return STATE_WAIT_FOR_BARCODE

        context.user_data["selected_product"] = product
        context.user_data["search_results"] = [product]

        await status_msg.delete()

        text = (
            f"✅ <b>Продукт найден!</b>\n\n"
            f"<b>{product['name']}</b>\n"
            f"🔥 {product.get('kcal_100g', 0):.0f} ккал на 100 г\n\n"
            f"Теперь укажи, сколько грамм ты съел."
        )

        await update.message.reply_text(
            text,
            reply_markup=get_weight_input_keyboard(),
            parse_mode="HTML"
        )

        return STATE_ENTER_WEIGHT

    async def _decode_barcode_from_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
        """Распознаёт штрихкод с фотографии."""
        try:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_bytes = await file.download_as_bytearray()
            image = Image.open(io.BytesIO(file_bytes))
            decoded_objects = decode(image)

            for obj in decoded_objects:
                barcode = obj.data.decode("utf-8")
                logger.info(f"Распознан штрихкод: {barcode}")
                return barcode

            return None

        except Exception as e:
            logger.error(f"Ошибка распознавания штрихкода: {e}")
            return None

    # ========== Избранное ==========

    async def _show_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает список избранных продуктов."""
        query = update.callback_query
        await query.answer()

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        favorites = await self.favorites_repo.get_favorites(user_id)

        if not favorites:
            text = (
                "⭐️ <b>Избранное</b>\n\n"
                "У тебя пока нет избранных продуктов.\n"
                "Добавляй блюда в избранное при записи."
            )
        else:
            text = "⭐️ <b>Твои избранные продукты:</b>\n\n"
            for fav in favorites[:10]:
                text += f"• <b>{fav['food_name']}</b> — {fav['amount_g']} г, {fav['kcal']} ккал\n"
            text += "\nНажми на продукт, чтобы добавить."

        await query.edit_message_text(
            text,
            reply_markup=get_favorites_keyboard(favorites),
            parse_mode="HTML"
        )
        return STATE_SELECT_FAVORITE

    async def select_favorite(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор из избранного."""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == "food_back_to_diary":
            return await self._back_to_diary(update, context)

        try:
            index = int(data.replace("food_fav_", ""))
        except ValueError:
            return STATE_SELECT_FAVORITE

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        favorites = await self.favorites_repo.get_favorites(user_id)

        if index >= len(favorites):
            return STATE_SELECT_FAVORITE

        fav = favorites[index]

        calculated = {
            "name": fav["food_name"],
            "weight": fav["amount_g"],
            "kcal": fav["kcal"],
            "protein": fav["protein_g"],
            "fat": fav["fat_g"],
            "carbs": fav["carbs_g"],
        }

        context.user_data["calculated_food"] = calculated
        await self.favorites_repo.increment_usage(fav["id"])

        return await self._ask_meal_type(update, context)

    # ========== Завершение ==========

    async def _back_to_diary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Возвращает в дневник и завершает диалог."""
        query = update.callback_query
        await query.answer()
        
        # Очищаем временные данные
        for key in ["search_results", "selected_product", "calculated_food", 
                    "meal_type", "food_weight", "last_added_food", "food_search_query"]:
            context.user_data.pop(key, None)
        
        # Получаем данные для дневника
        user = update.effective_user
        db = self.db
        user_repo = UserRepository(db)
        stats_repo = DailyStatsRepository(db)
        
        user_id = await user_repo.get_user_id(user.id)
        profile = await user_repo.get_profile(user_id)
        today_stats = await stats_repo.get_today_stats(user_id)
        
        name = user.first_name or "друг"
        greeting = f"🥑 <b>С возвращением, {name}!</b>"
        
        from handlers.start.utils import format_diary_compact, get_main_diary_keyboard
        
        diary_text = format_diary_compact(
            daily_kcal=profile["daily_kcal"],
            current_kcal=today_stats.get("kcal", 0),
            protein_goal=profile["daily_protein_g"],
            current_protein=today_stats.get("protein", 0),
            fat_goal=profile["daily_fat_g"],
            current_fat=today_stats.get("fat", 0),
            carbs_goal=profile["daily_carbs_g"],
            current_carbs=today_stats.get("carbs", 0),
            water_current=today_stats.get("water", 0),
        )
        
        text = f"{greeting}\n\n{diary_text}"
        
        await query.edit_message_text(
            text,
            reply_markup=get_main_diary_keyboard(),
            parse_mode="HTML"
        )
        
        return ConversationHandler.END

    async def add_another(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Добавить ещё одно блюдо."""
        query = update.callback_query
        await query.answer()

        for key in ["search_results", "selected_product", "calculated_food", 
                    "meal_type", "food_weight", "last_added_food"]:
            context.user_data.pop(key, None)

        return await self.show_add_food_menu(update, context)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отмена добавления еды."""
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text("❌ Добавление отменено.", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ Добавление отменено.", parse_mode="HTML")

        for key in ["search_results", "selected_product", "calculated_food", 
                    "meal_type", "food_weight", "last_added_food"]:
            context.user_data.pop(key, None)

        return ConversationHandler.END


def get_add_food_conversation_handler(db: Database) -> ConversationHandler:
    """Создаёт ConversationHandler для добавления еды."""
    handlers = AddFoodHandlers(db)

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.show_add_food_menu, pattern="^food_select_method$"),
            CallbackQueryHandler(handlers.add_another, pattern="^food_add_another$"),
        ],
        states={
            STATE_SELECT_METHOD: [
                CallbackQueryHandler(handlers.handle_method_selection, pattern="^food_method_"),
                CallbackQueryHandler(handlers._back_to_diary, pattern="^food_back_to_diary$"),
            ],
            STATE_WAIT_FOR_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_text_search),
                CallbackQueryHandler(handlers._back_to_diary, pattern="^food_back_to_diary$"),
            ],
            STATE_SELECT_PRODUCT: [
                CallbackQueryHandler(handlers.select_product, pattern="^food_product_"),
                CallbackQueryHandler(handlers._back_to_diary, pattern="^food_back_to_diary$"),
            ],
            STATE_ENTER_WEIGHT: [
                CallbackQueryHandler(handlers.process_weight_selection, pattern="^food_weight_"),
                CallbackQueryHandler(handlers.select_product, pattern="^food_back_to_products$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_custom_weight),
                CallbackQueryHandler(handlers._back_to_diary, pattern="^food_back_to_diary$"),
            ],
            STATE_SELECT_MEAL_TYPE: [
                CallbackQueryHandler(handlers.process_meal_type, pattern="^food_meal_"),
                CallbackQueryHandler(handlers._back_to_diary, pattern="^food_back_to_diary$"),
            ],
            STATE_CONFIRM_ADD: [
                CallbackQueryHandler(handlers.confirm_add, pattern="^food_confirm_add$"),
                CallbackQueryHandler(handlers.confirm_add, pattern="^food_change_weight$"),
                CallbackQueryHandler(handlers.handle_save_favorite, pattern="^food_save_favorite_"),
                CallbackQueryHandler(handlers._back_to_diary, pattern="^food_back_to_diary$"),
                CallbackQueryHandler(handlers.add_another, pattern="^food_add_another$"),
            ],
            STATE_WAIT_FOR_BARCODE: [
                MessageHandler(filters.PHOTO, handlers.process_barcode),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_barcode),
                CallbackQueryHandler(handlers._back_to_diary, pattern="^food_back_to_diary$"),
            ],
            STATE_SELECT_FAVORITE: [
                CallbackQueryHandler(handlers.select_favorite, pattern="^food_fav_"),
                CallbackQueryHandler(handlers.select_favorite, pattern="^food_noop$"),
                CallbackQueryHandler(handlers._back_to_diary, pattern="^food_back_to_diary$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handlers.cancel, pattern="^food_cancel$"),
            CallbackQueryHandler(handlers._back_to_diary, pattern="^food_back_to_diary$"),
            MessageHandler(filters.COMMAND, handlers.cancel),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )