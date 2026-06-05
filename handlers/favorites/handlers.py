"""
Обработчики для управления избранными блюдами.
"""
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CallbackQueryHandler, MessageHandler, filters
)

from db.database import Database
from db.repositories import (
    UserRepository, MealRepository,
    FavoritesRepository,
)
from .constants import (
    STATE_MAIN_MENU, STATE_ENTER_WEIGHT, STATE_SELECT_MEAL_TYPE,
    STATE_CONFIRM_ADD, STATE_AFTER_ADD,
    STATE_CONFIRM_DELETE, STATE_CONFIRM_CLEAR,
    CALLBACK_FAVORITES_SHOW, CALLBACK_FAVORITES_MENU,
    CALLBACK_FAVORITE_SELECT, CALLBACK_FAVORITE_DELETE,
    CALLBACK_FAVORITE_CONFIRM_DELETE, CALLBACK_FAVORITE_CLEAR_ALL,
    CALLBACK_FAVORITE_CONFIRM_CLEAR,
    CALLBACK_BACK_TO_DIARY,
    CALLBACK_PAGE_PREV, CALLBACK_PAGE_NEXT,
    CALLBACK_WEIGHT_PREFIX, CALLBACK_WEIGHT_CUSTOM,
    CALLBACK_MEAL_PREFIX,
    CALLBACK_CONFIRM_ADD, CALLBACK_CHANGE_WEIGHT,
    CALLBACK_ADD_ANOTHER, CALLBACK_SEARCH_AGAIN,
    CALLBACK_FAVORITE_CANCEL,
    MEAL_TYPES, PAGE_SIZE,
)
from .keyboards import (
    get_favorites_list_keyboard,
    get_weight_keyboard, get_meal_type_keyboard,
    get_confirm_keyboard, get_after_add_keyboard,
    get_confirm_delete_keyboard, get_confirm_clear_keyboard,
)

logger = logging.getLogger(__name__)


class FavoritesHandlers:
    """Обработчики для избранного."""

    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.meal_repo = MealRepository(db)
        self.favorites_repo = FavoritesRepository(db)

    # ================================================================
    # ВСПОМОГАТЕЛЬНЫЕ
    # ================================================================

    def _clear_context(self, context: ContextTypes.DEFAULT_TYPE):
        """Очищает временные данные."""
        for key in [
            "favorites_list", "favorites_page",
            "fav_selected", "fav_weight", "fav_meal_type",
        ]:
            context.user_data.pop(key, None)

    def _format_menu_text(self, favorites: list) -> str:
        """Форматирует текст главного меню."""
        if not favorites:
            return (
                "⭐ <b>Твоё избранное</b>\n\n"
                "😕 Пока здесь пусто.\n\n"
                "Когда добавляешь еду, я спрашиваю:\n"
                "<i>«Сохранить в избранное?»</i>\n\n"
                "Соглашайся — и любимые блюда будут здесь "
                "для быстрого добавления! 🚀"
            )

        total_kcal = sum(f.get("kcal", 0) for f in favorites)
        total_uses = sum(f.get("times_used", 1) for f in favorites)

        return (
            f"⭐ <b>Твоё избранное</b>\n\n"
            f"📊 Всего блюд: <b>{len(favorites)}</b>\n"
            f"🔥 Суммарно (порция): <b>{total_kcal}</b> ккал\n"
            f"🔁 Всего добавлений: <b>{total_uses}</b>\n\n"
            "Нажми на блюдо, чтобы добавить в дневник,\n"
            "или 🗑 чтобы удалить из избранного."
        )

    # ================================================================
    # ГЛАВНОЕ МЕНЮ
    # ================================================================

    async def show_favorites_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает главное меню избранного."""
        query = update.callback_query
        if query:
            await query.answer()

        # Очищаем временные данные (но не список)
        context.user_data.pop("fav_selected", None)
        context.user_data.pop("fav_weight", None)
        context.user_data.pop("fav_meal_type", None)

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)

        favorites = await self.favorites_repo.get_favorites(user_id, limit=200)

        context.user_data["favorites_list"] = favorites
        context.user_data["favorites_page"] = 0

        text = self._format_menu_text(favorites)

        target = query.edit_message_text if query else update.message.reply_text
        await target(
            text,
            reply_markup=get_favorites_list_keyboard(favorites, page=0),
            parse_mode="HTML"
        )
        return STATE_MAIN_MENU

    # ================================================================
    # ВЫБОР БЛЮДА → ВЕС → ТИП → ПОДТВЕРЖДЕНИЕ → СОХРАНЕНИЕ
    # ================================================================

    async def select_favorite(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Выбирает блюдо и переходит к выбору веса."""
        query = update.callback_query
        await query.answer("✓ Выбрано")

        try:
            fav_id = int(query.data.replace(CALLBACK_FAVORITE_SELECT, ""))
        except ValueError:
            return STATE_MAIN_MENU

        favorites = context.user_data.get("favorites_list", [])
        fav = next((f for f in favorites if f["id"] == fav_id), None)

        if not fav:
            await query.answer("❌ Блюдо не найдено", show_alert=True)
            return await self.show_favorites_menu(update, context)

        # Увеличиваем счётчик использований
        await self.favorites_repo.increment_usage(fav_id)

        context.user_data["fav_selected"] = fav

        return await self._ask_weight(update, context, fav)

    async def _ask_weight(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, fav: dict
    ) -> int:
        """Спрашивает вес порции."""
        query = update.callback_query
        default_weight = fav.get("amount_g", 100) or 100

        # Рассчитываем КБЖУ на 100г из данных порции
        multiplier = 100 / default_weight if default_weight > 0 else 1
        kcal_100g = fav["kcal"] * multiplier
        protein_100g = fav["protein_g"] * multiplier
        fat_100g = fav["fat_g"] * multiplier
        carbs_100g = fav["carbs_g"] * multiplier

        text = (
            f"⚖️ <b>Сколько грамм?</b>\n\n"
            f"🍽 <b>{fav['food_name']}</b>\n"
            f"💡 Обычно: ~{default_weight:.0f}г\n\n"
            f"<i>На 100г: 🔥{kcal_100g:.0f} ккал · "
            f"🍗{protein_100g:.1f}г · "
            f"🥑{fat_100g:.1f}г · "
            f"🍚{carbs_100g:.1f}г</i>\n\n"
            "Выбери вес или введи свой."
        )

        target = query.edit_message_text if query else update.message.reply_text
        await target(
            text,
            reply_markup=get_weight_keyboard(default_weight),
            parse_mode="HTML"
        )
        return STATE_ENTER_WEIGHT

    async def process_weight_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор веса (кнопки)."""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == CALLBACK_FAVORITES_MENU:
            return await self.show_favorites_menu(update, context)

        if data == CALLBACK_WEIGHT_CUSTOM:
            await query.edit_message_text(
                "✏️ <b>Введи вес в граммах</b>\n\n"
                "Только число, например: <code>150</code>",
                parse_mode="HTML"
            )
            return STATE_ENTER_WEIGHT

        if data.startswith(CALLBACK_WEIGHT_PREFIX):
            try:
                weight = float(data.replace(CALLBACK_WEIGHT_PREFIX, ""))
                if weight <= 0 or weight > 10000:
                    raise ValueError
            except ValueError:
                await query.answer("❌ Некорректный вес", show_alert=True)
                return STATE_ENTER_WEIGHT

            context.user_data["fav_weight"] = weight
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
                parse_mode="HTML"
            )
            return STATE_ENTER_WEIGHT

        context.user_data["fav_weight"] = weight
        await self._ask_meal_type_message(update, context)
        return STATE_SELECT_MEAL_TYPE

    async def _ask_meal_type(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает тип приёма пищи (callback)."""
        query = update.callback_query
        if query:
            await query.answer()

        text = self._format_meal_type_text(context)
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
        text = self._format_meal_type_text(context)
        await update.message.reply_text(
            text,
            reply_markup=get_meal_type_keyboard(),
            parse_mode="HTML"
        )

    def _format_meal_type_text(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Форматирует текст с рассчитанным КБЖУ."""
        fav = context.user_data.get("fav_selected", {})
        weight = context.user_data.get("fav_weight", 0)

        original_weight = fav.get("amount_g", 100) or 100
        multiplier = weight / original_weight if original_weight > 0 else 1

        kcal = round(fav.get("kcal", 0) * multiplier)
        protein = round(fav.get("protein_g", 0) * multiplier, 1)
        fat = round(fav.get("fat_g", 0) * multiplier, 1)
        carbs = round(fav.get("carbs_g", 0) * multiplier, 1)

        return (
            f"🍽️ <b>Когда ты это съел?</b>\n\n"
            f"🍳 <b>{fav.get('food_name', '')}</b>\n"
            f"⚖️ {weight:.0f}г\n\n"
            f"🔥 {kcal} ккал · "
            f"🍗 {protein}г · "
            f"🥑 {fat}г · "
            f"🍚 {carbs}г"
        )

    async def process_meal_type(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """🎯 Обрабатывает выбор типа приёма пищи и переходит к ПОДТВЕРЖДЕНИЮ."""
        query = update.callback_query
        await query.answer()

        if query.data == CALLBACK_FAVORITES_MENU:
            return await self.show_favorites_menu(update, context)

        # Кнопка "Изменить вес"
        if query.data == CALLBACK_WEIGHT_CUSTOM:
            fav = context.user_data.get("fav_selected", {})
            return await self._ask_weight(update, context, fav)

        if not query.data.startswith(CALLBACK_MEAL_PREFIX):
            return STATE_SELECT_MEAL_TYPE

        meal_type = query.data.replace(CALLBACK_MEAL_PREFIX, "")
        context.user_data["fav_meal_type"] = meal_type

        fav = context.user_data.get("fav_selected", {})
        weight = context.user_data.get("fav_weight", 0)
        meal_label = MEAL_TYPES.get(meal_type, meal_type)

        # Пересчёт КБЖУ
        original_weight = fav.get("amount_g", 100) or 100
        multiplier = weight / original_weight if original_weight > 0 else 1

        kcal = round(fav.get("kcal", 0) * multiplier)
        protein = round(fav.get("protein_g", 0) * multiplier, 1)
        fat = round(fav.get("fat_g", 0) * multiplier, 1)
        carbs = round(fav.get("carbs_g", 0) * multiplier, 1)

        # 🎯 НОВОЕ: показываем экран ПОДТВЕРЖДЕНИЯ
        text = (
            f"✅ <b>Проверь данные</b>\n\n"
            f"🍳 <b>{fav.get('food_name', '')}</b>\n"
            f"⚖️ {weight:.0f}г\n"
            f"🍽 {meal_label}\n\n"
            f"🔥 {kcal} ккал · "
            f"🍗 {protein}г · "
            f"🥑 {fat}г · "
            f"🍚 {carbs}г\n\n"
            "Всё верно?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_confirm_keyboard(),
            parse_mode="HTML"
        )
        return STATE_CONFIRM_ADD

    # ================================================================
    # ПОДТВЕРЖДЕНИЕ И СОХРАНЕНИЕ (НОВОЕ)
    # ================================================================

    async def confirm_add(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """🎯 Подтверждает и сохраняет блюдо с красивым экраном успеха."""
        query = update.callback_query
        await query.answer("✓ Сохраняю...")

        data = query.data

        # Кнопка "Изменить вес"
        if data == CALLBACK_CHANGE_WEIGHT:
            fav = context.user_data.get("fav_selected", {})
            return await self._ask_weight(update, context, fav)

        # Кнопка "Отмена"
        if data == CALLBACK_FAVORITES_MENU:
            return await self.show_favorites_menu(update, context)

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)

        fav = context.user_data.get("fav_selected", {})
        weight = context.user_data.get("fav_weight", 0)
        meal_type = context.user_data.get("fav_meal_type", "snack")

        if not fav or weight <= 0:
            await query.answer("❌ Ошибка данных", show_alert=True)
            return await self.show_favorites_menu(update, context)

        # Пересчёт КБЖУ
        original_weight = fav.get("amount_g", 100) or 100
        multiplier = weight / original_weight if original_weight > 0 else 1

        kcal = round(fav.get("kcal", 0) * multiplier)
        protein = round(fav.get("protein_g", 0) * multiplier, 1)
        fat = round(fav.get("fat_g", 0) * multiplier, 1)
        carbs = round(fav.get("carbs_g", 0) * multiplier, 1)

        # Сохраняем в meals
        await self.meal_repo.add_meal(
            user_id=user_id,
            meal_type=meal_type,
            food_name=fav["food_name"],
            amount_g=weight,
            kcal=kcal,
            protein_g=protein,
            fat_g=fat,
            carbs_g=carbs,
            barcode=fav.get("barcode")
        )

        meal_label = MEAL_TYPES.get(meal_type, meal_type)

        # 🎯 Красивый экран успеха (магия Apple)
        text = (
            f"🎉 <b>Готово!</b>\n\n"
            f"✅ Добавлено в <b>{meal_label}</b>\n\n"
            f"🍳 <b>{fav['food_name']}</b>\n"
            f"⚖️ {weight:.0f}г\n"
            f"🔥 {kcal} ккал · "
            f"🍗 {protein}г · "
            f"🥑 {fat}г · "
            f"🍚 {carbs}г\n\n"
            "Что хочешь сделать?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_after_add_keyboard(),
            parse_mode="HTML"
        )

        return STATE_AFTER_ADD

    # ================================================================
    # СОСТОЯНИЕ ПОСЛЕ ДОБАВЛЕНИЯ (НОВОЕ)
    # ================================================================

    async def handle_after_add(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """🎯 Обрабатывает действия после успешного добавления."""
        query = update.callback_query
        await query.answer()

        data = query.data

        # Очистка временных данных
        context.user_data.pop("fav_selected", None)
        context.user_data.pop("fav_weight", None)
        context.user_data.pop("fav_meal_type", None)

        if data == CALLBACK_ADD_ANOTHER:
            # Добавить ещё одно блюдо — выходим в add_food
            from handlers.add_food.handlers import AddFoodHandlers
            add_food_handler = AddFoodHandlers(self.db)
            await add_food_handler.show_add_food_menu(update, context)
            return ConversationHandler.END

        if data == CALLBACK_SEARCH_AGAIN:
            # Поискать что-то другое — тоже в add_food
            from handlers.add_food.handlers import AddFoodHandlers
            add_food_handler = AddFoodHandlers(self.db)
            await add_food_handler.show_add_food_menu(update, context)
            return ConversationHandler.END

        if data == CALLBACK_FAVORITES_MENU:
            # Вернуться к избранному
            return await self.show_favorites_menu(update, context)

        if data == CALLBACK_BACK_TO_DIARY:
            # В дневник
            return await self.back_to_diary(update, context)

        return STATE_AFTER_ADD

    # ================================================================
    # УДАЛЕНИЕ БЛЮДА
    # ================================================================

    async def ask_delete_favorite(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Запрашивает подтверждение удаления блюда."""
        query = update.callback_query
        await query.answer()

        try:
            fav_id = int(query.data.replace(CALLBACK_FAVORITE_DELETE, ""))
        except ValueError:
            return STATE_MAIN_MENU

        favorites = context.user_data.get("favorites_list", [])
        fav = next((f for f in favorites if f["id"] == fav_id), None)

        if not fav:
            await query.answer("❌ Блюдо не найдено", show_alert=True)
            return STATE_MAIN_MENU

        text = (
            f"🗑 <b>Удалить из избранного?</b>\n\n"
            f"⭐ <b>{fav['food_name']}</b>\n"
            f"⚖️ {fav['amount_g']:.0f}г · 🔥 {fav['kcal']} ккал\n\n"
            f"Использовалось раз: <b>{fav.get('times_used', 1)}</b>\n\n"
            "⚠️ Это действие нельзя отменить."
        )

        await query.edit_message_text(
            text,
            reply_markup=get_confirm_delete_keyboard(fav_id),
            parse_mode="HTML"
        )
        return STATE_CONFIRM_DELETE

    async def confirm_delete_favorite(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Подтверждает удаление блюда."""
        query = update.callback_query
        await query.answer("🗑 Удаляю...")

        try:
            fav_id = int(query.data.replace(CALLBACK_FAVORITE_CONFIRM_DELETE, ""))
        except ValueError:
            return await self.show_favorites_menu(update, context)

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)

        deleted = await self.favorites_repo.delete_favorite(user_id, fav_id)

        if deleted:
            await query.answer("✅ Удалено из избранного", show_alert=False)
        else:
            await query.answer("❌ Ошибка удаления", show_alert=True)

        return await self.show_favorites_menu(update, context)

    # ================================================================
    # ОЧИСТКА ВСЕГО ИЗБРАННОГО
    # ================================================================

    async def ask_clear_all(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Запрашивает подтверждение очистки."""
        query = update.callback_query
        await query.answer()

        favorites = context.user_data.get("favorites_list", [])

        text = (
            f"🗑 <b>Очистить всё избранное?</b>\n\n"
            f"Будет удалено <b>{len(favorites)}</b> блюд.\n\n"
            "⚠️ Это действие нельзя отменить!"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_confirm_clear_keyboard(),
            parse_mode="HTML"
        )
        return STATE_CONFIRM_CLEAR

    async def confirm_clear_all(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Подтверждает очистку всего избранного."""
        query = update.callback_query
        await query.answer("🗑 Очищаю...")

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)

        try:
            deleted_count = await self.favorites_repo.clear_all(user_id)
            await query.answer(
                f"✅ Удалено {deleted_count} блюд",
                show_alert=False
            )
        except Exception as e:
            logger.error(f"Ошибка очистки избранного: {e}")
            await query.answer("❌ Ошибка", show_alert=True)

        return await self.show_favorites_menu(update, context)

    # ================================================================
    # ПАГИНАЦИЯ
    # ================================================================

    async def handle_pagination(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает навигацию по страницам."""
        query = update.callback_query
        await query.answer()

        favorites = context.user_data.get("favorites_list", [])
        current_page = context.user_data.get("favorites_page", 0)
        total_pages = max(1, (len(favorites) + PAGE_SIZE - 1) // PAGE_SIZE)

        if query.data == CALLBACK_PAGE_PREV:
            new_page = max(0, current_page - 1)
        elif query.data == CALLBACK_PAGE_NEXT:
            new_page = min(total_pages - 1, current_page + 1)
        else:
            return STATE_MAIN_MENU

        context.user_data["favorites_page"] = new_page

        text = self._format_menu_text(favorites)

        await query.edit_message_text(
            text,
            reply_markup=get_favorites_list_keyboard(favorites, page=new_page),
            parse_mode="HTML"
        )
        return STATE_MAIN_MENU

    # ================================================================
    # ОТМЕНА И ВОЗВРАТ
    # ================================================================

    async def cancel_action(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отмена текущего действия."""
        query = update.callback_query
        if query:
            await query.answer("❌ Отменено")
        return await self.show_favorites_menu(update, context)

    async def back_to_diary(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Возврат в дневник."""
        query = update.callback_query
        if query:
            await query.answer()

        self._clear_context(context)

        from handlers.start.handlers import show_diary
        await show_diary(update, context)
        return ConversationHandler.END


# ================================================================
# РЕГИСТРАЦИЯ ConversationHandler
# ================================================================

def get_favorites_handler(db: Database) -> ConversationHandler:
    """Создаёт ConversationHandler для избранного."""
    h = FavoritesHandlers(db)

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                h.show_favorites_menu,
                pattern=f"^{CALLBACK_FAVORITES_SHOW}$"
            ),
            # 🎯 НОВОЕ: entry point из add_food через "Избранное"
            CallbackQueryHandler(
                h.show_favorites_menu,
                pattern=f"^favorites_show$"
            ),
        ],
        states={
            STATE_MAIN_MENU: [
                CallbackQueryHandler(h.select_favorite, pattern=f"^{CALLBACK_FAVORITE_SELECT}"),
                CallbackQueryHandler(h.ask_delete_favorite, pattern=f"^{CALLBACK_FAVORITE_DELETE}"),
                CallbackQueryHandler(h.ask_clear_all, pattern=f"^{CALLBACK_FAVORITE_CLEAR_ALL}$"),
                CallbackQueryHandler(
                    h.handle_pagination,
                    pattern=f"^({CALLBACK_PAGE_PREV}|{CALLBACK_PAGE_NEXT})$"
                ),
                CallbackQueryHandler(h.back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
                CallbackQueryHandler(h.show_favorites_menu, pattern=f"^{CALLBACK_FAVORITES_MENU}$"),
            ],
            STATE_ENTER_WEIGHT: [
                CallbackQueryHandler(
                    h.process_weight_selection,
                    pattern=f"^({CALLBACK_WEIGHT_PREFIX}|{CALLBACK_WEIGHT_CUSTOM}|{CALLBACK_FAVORITES_MENU})"
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    h.process_custom_weight
                ),
            ],
            STATE_SELECT_MEAL_TYPE: [
                CallbackQueryHandler(
                    h.process_meal_type,
                    pattern=f"^({CALLBACK_MEAL_PREFIX}|{CALLBACK_FAVORITES_MENU}|{CALLBACK_WEIGHT_CUSTOM})"
                ),
            ],
            # 🎯 НОВОЕ: состояние подтверждения
            STATE_CONFIRM_ADD: [
                CallbackQueryHandler(
                    h.confirm_add,
                    pattern=f"^({CALLBACK_CONFIRM_ADD}|{CALLBACK_CHANGE_WEIGHT}|{CALLBACK_FAVORITES_MENU})$"
                ),
            ],
            # 🎯 НОВОЕ: состояние после добавления
            STATE_AFTER_ADD: [
                CallbackQueryHandler(
                    h.handle_after_add,
                    pattern=f"^({CALLBACK_ADD_ANOTHER}|{CALLBACK_SEARCH_AGAIN}|{CALLBACK_FAVORITES_MENU}|{CALLBACK_BACK_TO_DIARY})$"
                ),
            ],
            STATE_CONFIRM_DELETE: [
                CallbackQueryHandler(h.confirm_delete_favorite, pattern=f"^{CALLBACK_FAVORITE_CONFIRM_DELETE}"),
                CallbackQueryHandler(
                    h.cancel_action,
                    pattern=f"^({CALLBACK_FAVORITE_CANCEL}|{CALLBACK_FAVORITES_MENU})$"
                ),
            ],
            STATE_CONFIRM_CLEAR: [
                CallbackQueryHandler(h.confirm_clear_all, pattern=f"^{CALLBACK_FAVORITE_CONFIRM_CLEAR}$"),
                CallbackQueryHandler(
                    h.cancel_action,
                    pattern=f"^({CALLBACK_FAVORITE_CANCEL}|{CALLBACK_FAVORITES_MENU})$"
                ),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(h.back_to_diary, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            MessageHandler(filters.COMMAND, h.back_to_diary),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )