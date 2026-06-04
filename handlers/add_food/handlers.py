import io
import logging
from typing import Optional
from PIL import Image
from pyzbar.pyzbar import decode
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    get_favorites_keyboard, get_custom_weight_keyboard, get_recent_foods_keyboard
)
from handlers.add_food.api_client import OpenFoodFactsClient, OFFProduct
from handlers.add_food.utils import parse_food_text, DEFAULT_UNITS
from handlers.add_food.food_matcher import SmartFoodMatcher, UNIT_CONVERSION_MAP
from handlers.add_food.local_foods import POPULAR_FOODS

logger = logging.getLogger(__name__)


class AddFoodHandlers:
    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.meal_repo = MealRepository(db)
        self.favorites_repo = FavoritesRepository(db)
        self.stats_repo = DailyStatsRepository(db)
        
        self.api_client = OpenFoodFactsClient()
        self.food_matcher = SmartFoodMatcher(POPULAR_FOODS)
        
        # Хранение истории поиска
        self._recent_searches: dict = {}
        self._recent_limit = 10

    # ========== Входная точка ==========
    
    async def show_add_food_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает меню выбора способа добавления еды."""
        query = update.callback_query
        await query.answer()
        
        # Получаем недавние продукты
        user_id = str(update.effective_user.id)
        recent_foods = self._recent_searches.get(user_id, [])[:8]
        
        text = (
            "<b>🍽️ Добавление еды</b>\n\n"
            "Как удобнее записать приём пищи?"
        )
        
        if recent_foods:
            text += "\n\n<b>🕒 Недавнее:</b>"
            for food in recent_foods:
                text += f"\n• {food['name']} ({food['weight']}г)"
            text += "\n\n"
            
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
        elif method == "food_method_recent":
            return await self._show_recent_foods(update, context)
        elif method == "food_back_to_diary":
            return await self._back_to_diary(update, context)
            
        return STATE_SELECT_METHOD

    # ========== Недавнее ==========
    
    async def _show_recent_foods(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает список недавних блюд."""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        recent_foods = self._recent_searches.get(user_id, [])
        
        if not recent_foods:
            await query.edit_message_text(
                "🕒 <b>Нет недавних блюд</b>\n\n"
                "Добавьте хоть раз еду, и она появится здесь для быстрого доступа.",
                parse_mode="HTML"
            )
            return STATE_SELECT_METHOD
            
        await query.edit_message_text(
            "<b>🕒 Ваши недавние блюда:</b>\n\n"
            "Выберите одно из списка:",
            reply_markup=get_recent_foods_keyboard(recent_foods),
            parse_mode="HTML"
        )
        return STATE_SELECT_FAVORITE

    async def select_recent_food(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Выбор из недавнего."""
        query = update.callback_query
        await query.answer()
        
        try:
            index = int(query.data.replace("food_recent_", ""))
            user_id = str(update.effective_user.id)
            recent_foods = self._recent_searches.get(user_id, [])
            
            if index >= len(recent_foods):
                return STATE_SELECT_FAVORITE
                
            selected = recent_foods[index]
            context.user_data["calculated_food"] = selected
            
            return await self._ask_meal_type(update, context)
            
        except (ValueError, IndexError):
            return STATE_SELECT_FAVORITE

    # ========== Популярные блюда ==========
    
    async def _show_popular_foods(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает популярные блюда из локальной базы."""
        query = update.callback_query
        await query.answer()
        
        popular = POPULAR_FOODS[:15]
        context.user_data["search_results"] = popular
        context.user_data["search_page"] = 1
        
        text = "<b>🔥 Популярные блюда</b>\n\n"
        
        for i, product in enumerate(popular):
            name = product.get("name", "")[:40]
            brand = product.get("brand", "")
            kcal = product.get("kcal_100g", 0)
            weight_def = product.get("default_weight", 100)
            
            text += f"<b>{i + 1}</b> {name}\n"
            text += f"🔥 {int(kcal)} ккал | 🍗 {product.get('protein_100g', 0):.1f}г | 🥑 {product.get('fat_100g', 0):.1f}г | 🍚 {product.get('carbs_100g', 0):.1f}г\n\n"
            
        text += "\nВыберите блюдо из списка:"
        
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
            "<b>✍️ Что вы съели?</b>\n\n"
            "Напишите название блюда или продукта. Можно указать вес.\n\n"
            "<b>Примеры:</b>\n"
            "• <code>гречка с котлетой 300г</code>\n"
            "• <code>омлет из двух яиц с сыром</code>\n"
            "• <code>банан</code>\n\n"
            "Я найду калорийность и предложу варианты."
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_back_keyboard("food_back_to_diary"),
            parse_mode="HTML"
        )
        return STATE_WAIT_FOR_TEXT

    async def process_text_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка текстового запроса."""
        user_input = update.message.text.strip()
        
        # Предобработка запроса
        food_name, weight, unit = self.food_matcher.preprocess_query(user_input)
        
        # Сохраняем данные в контекст
        context.user_data["food_search_query"] = food_name
        if weight:
            context.user_data["food_weight"] = weight
        if unit:
            context.user_data["food_unit"] = unit
            
        # Отправляем статус "печатает..."
        await update.message.reply_chat_action(action="typing")
        
        # Поиск
        products = await self.food_matcher.search_with_api_fallback(food_name, self.api_client)
        
        if not products:
            # Генерируем подсказки
            alternatives = self.food_matcher.suggest_alternatives(food_name)
            alt_text = "\n\n<b>Возможно, вы искали:</b>" + \
                      "".join(f"\n• {alt}" for alt in alternatives[:3])
                      
            await update.message.reply_text(
                f"❌ По запросу «<i>{food_name}</i>» ничего не найдено." + alt_text,
                parse_mode="HTML"
            )
            return STATE_WAIT_FOR_TEXT
            
        # Добавляем в историю
        user_id = str(update.effective_user.id)
        if user_id not in self._recent_searches:
            self._recent_searches[user_id] = []
            
        # Берём первый результат для истории
        if products:
            self._recent_searches[user_id].append(products[0])
            # Храним максимум 20 записей
            self._recent_searches[user_id] = self._recent_searches[user_id][-20:]
            
        context.user_data["search_results"] = products
        context.user_data["search_page"] = 1
        
        # Отправляем результат
        await update.message.reply_text(
            f"🔍 Найдено продуктов по запросу «<i>{food_name}</i>»:\n\n",
            reply_markup=get_product_selection_keyboard(products),
            parse_mode="HTML"
        )
        return STATE_SELECT_PRODUCT

    # ========== Выбор продукта ==========
    
    async def select_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора продукта."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("food_product_"):
            try:
                index = int(data.replace("food_product_", ""))
            except ValueError:
                return STATE_SELECT_PRODUCT
                
            products = context.user_data.get("search_results", [])
            if index >= len(products):
                return STATE_SELECT_PRODUCT
                
            selected = products[index]
            context.user_data["selected_product"] = selected
            
            # Проверяем, есть ли заранее указанный вес
            if "food_weight" in context.user_data:
                weight = context.user_data["food_weight"]
                calculated = self.api_client.calculate_for_weight(selected, weight)
                context.user_data["calculated_food"] = calculated
                return await self._ask_meal_type(update, context)
            else:
                return await self._ask_weight(update, context)
                
        elif data.startswith("food_products_next_"):
            page = int(data.replace("food_products_next_", ""))
            context.user_data["search_page"] = page
            products = context.user_data.get("search_results", [])
            await query.edit_message_text(
                f"Выбрать продукт (страница {page}):",
                reply_markup=get_product_selection_keyboard(products, page),
                parse_mode="HTML"
            )
            return STATE_SELECT_PRODUCT
            
        elif data.startswith("food_products_prev_"):
            page = int(data.replace("food_products_prev_", ""))
            context.user_data["search_page"] = max(1, page)
            products = context.user_data.get("search_results", [])
            await query.edit_message_text(
                f"Выбрать продукт (страница {page}):",
                reply_markup=get_product_selection_keyboard(products, page),
                parse_mode="HTML"
            )
            return STATE_SELECT_PRODUCT
            
        return STATE_SELECT_PRODUCT

    # ========== Выбор веса ==========
    
    async def _ask_weight(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Спрашивает вес продукта."""
        query = update.callback_query
        product = context.user_data.get("selected_product", {})
        default_weight = product.get("default_weight", 100)
        
        text = (
            f"<b>⚖️ Укажите вес порции</b>\n\n"
            f"<b>{product.get('name', '')}</b>\n\n"
            f"Вес по умолчанию: {int(default_weight)} г\n\n"
            "Выберите из вариантов или введите свой."
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_weight_input_keyboard(default_weight),
            parse_mode="HTML"
        )
        return STATE_ENTER_WEIGHT

    async def process_weight_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора веса."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("food_weight_default_"):
            weight = float(data.replace("food_weight_default_", ""))
        elif data.startswith("food_weight_"):
            weight = float(data.replace("food_weight_", ""))
        elif data == "food_weight_custom":
            await query.edit_message_text(
                "<b>✏️ Введите вес в граммах</b>\n"
                "Например: <code>150</code>",
                reply_markup=get_custom_weight_keyboard(),
                parse_mode="HTML"
            )
            return STATE_ENTER_WEIGHT
        elif data.startswith("food_fav_change_weight_"):
            # Для избранного - показываем тот же экран веса
            index = data.replace("food_fav_change_weight_", "")
            await self._ask_weight(update, context)
            return STATE_ENTER_WEIGHT
        else:
            return STATE_ENTER_WEIGHT
            
        product = context.user_data.get("selected_product", {})
        calculated = self.api_client.calculate_for_weight(product, weight)
        context.user_data["calculated_food"] = calculated
        return await self._ask_meal_type(update, context)

    async def process_custom_weight(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка ручного ввода веса."""
        user_input = update.message.text.strip()
        
        try:
            weight = float(user_input)
            if weight <= 0 or weight > 10000:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Введите положительное число (граммы).\nПример: <code>150</code>",
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
        """Спрашивает тип приёма пищи."""
        query = update.callback_query
        calculated = context.user_data.get("calculated_food", {})
        
        meal_icons = {
            "breakfast": "🥐",
            "lunch": "🍲",
            "dinner": "🍽️",
            "snack": "🍎",
        }
        
        icon = meal_icons.get(context.user_data.get("meal_type", ""), "🍽️")
        
        text = (
            f"<b>🍽️ Когда вы это съели?</b>\n\n"
            f"<b>{calculated.get('name', '')}</b>\n"
            f"Вес: {calculated.get('weight', 0):.0f} г\n"
            f"{icon} {calculated.get('kcal', 0)} ккал | "
            f"🍗 {calculated.get('protein', 0):.1f}г | "
            f"🥑 {calculated.get('fat', 0):.1f}г | "
            f"🍚 {calculated.get('carbs', 0):.1f}г\n\n"
            "Выберите тип приёма пищи:"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_meal_type_keyboard(),
            parse_mode="HTML"
        )
        return STATE_SELECT_MEAL_TYPE

    async def _ask_meal_type_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Спрашивает тип приёма пищи (для message handlers)."""
        calculated = context.user_data.get("calculated_food", {})
        
        text = (
            f"<b>🍽️ Когда вы это съели?</b>\n\n"
            f"<b>{calculated.get('name', '')}</b>\n"
            f"Вес: {calculated.get('weight', 0):.0f} г\n"
            f"🔥 {calculated.get('kcal', 0)} ккал | "
            f"🍗 {calculated.get('protein', 0):.1f}г | "
            f"🥑 {calculated.get('fat', 0):.1f}г | "
            f"🍚 {calculated.get('carbs', 0):.1f}г\n\n"
            "Выберите тип приёма пищи:"
        )
        
        await update.message.reply_text(
            text,
            reply_markup=get_meal_type_keyboard(),
            parse_mode="HTML"
        )

    async def process_meal_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора типа приёма пищи."""
        query = update.callback_query
        await query.answer()
        
        meal_type = query.data.replace("food_meal_", "").replace("-", "_")
        context.user_data["meal_type"] = meal_type
        
        calculated = context.user_data.get("calculated_food", {})
        meal_label = MEAL_TYPES.get(meal_type, meal_type)
        
        text = (
            f"<b>✅ Подтверждение</b>\n\n"
            f"<b>{calculated.get('name', '')}</b>\n"
            f"Вес: {calculated.get('weight', 0):.0f} г\n"
            f"Тип: {meal_label}\n\n"
            f"🔥 {calculated.get('kcal', 0)} ккал | "
            f"🍗 {calculated.get('protein', 0):.1f}г | "
            f"🥑 {calculated.get('fat', 0):.1f}г | "
            f"🍚 {calculated.get('carbs', 0):.1f}г\n\n"
            "Всё верно?"
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
        
        # Сохраняем в базу
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
        for key in ["search_results", "selected_product", "calculated_food", "meal_type", "food_weight", "food_search_query"]:
            context.user_data.pop(key, None)
        
        meal_label = MEAL_TYPES.get(meal_type, meal_type)
        
        # Обновляем статистику пользователя
        await self.update_user_stats(user_id)
        
        text = (
            f"✅ <b>Добавлено в {meal_label}!</b>\n\n"
            f"🍳 <b>{calculated['name']}</b>\n"
            f"🔥 {calculated['kcal']} ккал | "
            f"🍗 {calculated['protein']:.1f}г | "
            f"🥑 {calculated['fat']:.1f}г | "
            f"🍚 {calculated['carbs']:.1f}г\n\n"
            f"─────────────────\n\n"
            "Хотите сохранить это блюдо в избранное?"
        )
        
        context.user_data["last_added_food"] = {
            "name": calculated["name"],
            "weight": calculated["weight"],
            "kcal": calculated["kcal"],
            "protein": calculated["protein"],
            "fat": calculated["fat"],
            "carbs": calculated["carbs"],
            "barcode": selected_product.get("code")
        }
        
        await query.edit_message_text(
            text,
            reply_markup=get_save_favorite_keyboard(),
            parse_mode="HTML"
        )
        return STATE_CONFIRM_ADD

    async def handle_save_favorite(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка сохранения в избранное."""
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
                amount_g=food_data["weight"],
                kcal=food_data["kcal"],
                protein_g=food_data["protein"],
                fat_g=food_data["fat"],
                carbs_g=food_data["carbs"],
                barcode=food_data.get("barcode")
            )
            
        context.user_data.pop("last_added_food", None)
        
        text = (
            f"✅ <b>Блюдо добавлено!</b>\n\n"
            "Что хотите сделать дальше?"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_after_add_keyboard(),
            parse_mode="HTML"
        )
        return STATE_CONFIRM_ADD

    async def update_user_stats(self, user_id: int) -> None:
        """Обновляет статистику пользователя."""
        today_stats = await self.stats_repo.get_today_stats(user_id)
        await self.stats_repo.update_today_stats(
            user_id=user_id,
            added_kcal=today_stats.get("kcal", 0),
            added_protein=today_stats.get("protein", 0),
            added_fat=today_stats.get("fat", 0),
            added_carbs=today_stats.get("carbs", 0),
        )

    # ========== Штрихкод ==========
    
    async def _start_barcode_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начинает сканирование штрихкода."""
        query = update.callback_query
        
        text = (
            "<b>📷 Сканирование штрихкода</b>\n\n"
            "Отправьте фото штрихкода или напишите цифры вручную."
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_barcode_back_keyboard(),
            parse_mode="HTML"
        )
        return STATE_WAIT_FOR_BARCODE

    async def process_barcode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка штрихкода."""
        query = update.callback_query if hasattr(update, 'callback_query') and update.callback_query else None
        
        if update.message.photo:
            status_msg = await update.message.reply_text("🔍 Распознаю штрихкод...")
            barcode = await self._decode_barcode_from_photo(update, context)
            
            if not barcode:
                await status_msg.edit_text(
                    "❌ Не удалось распознать штрихкод.\n"
                    "Попробуйте ввести цифры вручную.",
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
                "❌ Продукт не найден.\nПопробуйте найти вручную через текстовый поиск.",
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
            "Теперь укажите, сколько грамм вы съели."
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
                "<b>⭐️ Избранное</b>\n\n"
                "У вас пока нет избранных продуктов.\n"
                "Добавляйте блюда при записи."
            )
        else:
            text = "<b>⭐️ Ваши избранные продукты:</b>\n\n"
            for fav in favorites[:10]:
                text += f"• <b>{fav['food_name']}</b> — {fav['amount_g']} г, {fav['kcal']} ккал\n"
            text += "\nНажмите на продукт, чтобы добавить."
            
        await query.edit_message_text(
            text,
            reply_markup=get_favorites_keyboard(favorites),
            parse_mode="HTML"
        )
        return STATE_SELECT_FAVORITE

    async def select_favorite(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора из избранного."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("food_fav_"):
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
            
        elif data == "food_fav_change_weight_":
            return await self._ask_weight(update, context)
            
        return STATE_SELECT_FAVORITE

    # ========== Завершение ==========
    
    async def _back_to_diary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Возвращает в дневник."""
        query = update.callback_query
        await query.answer()
        
        # Очищаем контекст
        for key in ["search_results", "selected_product", "calculated_food", "meal_type", "food_weight", "last_added_food"]:
            context.user_data.pop(key, None)
            
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        
        profile = await self.user_repo.get_profile(user_id)
        today_stats = await self.stats_repo.get_today_stats(user_id)
        
        name = user.first_name or "друг"
        greeting = f"🥑 <b>С возвращением, {name}!</b>\n\n"
        
        from handlers.start.utils import format_diary_compact, get_main_diary_keyboard
        
        diary_text = format_diary_compact(
            daily_kcal=profile.get("daily_kcal", 0),
            current_kcal=today_stats.get("kcal", 0),
            protein_goal=profile.get("daily_protein_g", 0),
            current_protein=today_stats.get("protein", 0),
            fat_goal=profile.get("daily_fat_g", 0),
            current_fat=today_stats.get("fat", 0),
            carbs_goal=profile.get("daily_carbs_g", 0),
            current_carbs=today_stats.get("carbs", 0),
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
        
        for key in ["search_results", "selected_product", "calculated_food", "meal_type", "food_weight", "last_added_food"]:
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
            
        for key in ["search_results", "selected_product", "calculated_food", "meal_type", "food_weight"]:
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
                CallbackQueryHandler(handlers.select_recent_food, pattern="^food_recent_"),
            ],
            STATE_WAIT_FOR_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_text_search),
                CallbackQueryHandler(handlers._back_to_diary, pattern="^food_back_to_diary$"),
            ],
            STATE_SELECT_PRODUCT: [
                CallbackQueryHandler(handlers.select_product, pattern="^food_product_|^food_products_"),
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