from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any

# Стандартные веса для кнопок
WEIGHT_PRESETS = [50, 100, 150, 200, 250, 300, 350, 400]


def get_select_method_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора способа добавления еды."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📷 Сканировать штрихкод", callback_data="food_method_barcode")],
        [InlineKeyboardButton("✍️ Написать текстом", callback_data="food_method_text")],
        [InlineKeyboardButton("⭐️ Выбрать из избранного", callback_data="food_method_favorites")],
        [InlineKeyboardButton("🔥 Популярные блюда", callback_data="food_method_popular")],
        [InlineKeyboardButton("🕒 Недавнее", callback_data="food_method_recent")],
        [InlineKeyboardButton("🔙 ← Назад в дневник", callback_data="food_back_to_diary")],
    ])


def get_back_keyboard(callback_data: str = "food_back_to_diary") -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой Назад."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 ← Назад", callback_data=callback_data)]
    ])


def get_meal_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа приёма пищи."""
    buttons = [
        ["🥐 Завтрак", "🍲 Обед"],
        ["🍽️ Ужин", "🍎 Перекус"],
    ]
    buttons.append(["🔙 ← Назад"])
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=f"food_meal_{label.replace(' ', '_').lower()}") for label in row] for row in buttons[:-1]])


def get_product_selection_keyboard(products: List[Dict[str, Any]], page: int = 1, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура для выбора продукта с поддержкой пагинации."""
    buttons = []
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, len(products))
    
    for i, product in enumerate(products[start_idx:end_idx]):
        name = product.get("name", "Неизвестный")[:30]
        brand = product.get("brand", "")
        kcal = product.get("kcal_100g", 0)
        
        display_name = f"{name}"
        if brand:
            display_name += f"\n({brand})"
            
        button_text = f"#{start_idx + i + 1} {display_name} (~{int(kcal)} ккал/100г)"
        buttons.append([InlineKeyboardButton(button_text, callback_data=f"food_product_{start_idx + i}")])
    
    # Пагинация
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"food_products_prev_{page - 1}"))
    if end_idx < len(products):
        pagination_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"food_products_next_{page + 1}"))
        
    if pagination_buttons:
        buttons.append(pagination_buttons)
        
    buttons.append(get_back_keyboard("food_back_to_diary"))
    return InlineKeyboardMarkup(buttons)


def get_weight_input_keyboard(default_weight: float = 100) -> InlineKeyboardMarkup:
    """Клавиатура для ввода веса с умными пресетами."""
    # Адаптивные пресеты вокруг дефолтного веса
    presets = [50, 100, 150, 200, 250, 300, 350, 400]
    if 200 <= default_weight < 300:
        presets = [150, 200, 250, 300, 350]
    elif default_weight >= 400:
        presets = [350, 400, 450, 500, 600, 700, 800]
    
    buttons = []
    rows = []
    for preset in presets:
        rows.append(preset)
        if len(rows) == 3:
            buttons.append([InlineKeyboardButton(f"{r} г", callback_data=f"food_weight_{r}") for r in rows])
            rows = []
    if rows:
        buttons.append([InlineKeyboardButton(f"{r} г", callback_data=f"food_weight_{r}") for r in rows])
        
    buttons.append([
        InlineKeyboardButton("✏️ Ввести свой вес", callback_data="food_weight_custom"),
        InlineKeyboardButton("📏 Стандартная порция", callback_data=f"food_weight_default_{int(default_weight)}")
    ])
    buttons.append(get_back_keyboard("food_select_products"))
    return InlineKeyboardMarkup(buttons)


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения добавления."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить", callback_data="food_confirm_add")],
        [InlineKeyboardButton("✏️ Изменить вес", callback_data="food_change_weight")],
        [InlineKeyboardButton("👁️ Показать ингредиенты", callback_data="food_show_details")],
    ])


def get_after_add_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после успешного добавления."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📔 Вернуться в дневник", callback_data="food_back_to_diary")],
        [InlineKeyboardButton("🍽️ Добавить ещё блюдо", callback_data="food_add_another")],
    ])


def get_save_favorite_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура сохранения в избранное."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐️ Да, сохранить", callback_data="food_save_favorite_yes")],
        [InlineKeyboardButton("👌 Нет, спасибо", callback_data="food_save_favorite_no")],
    ])


def get_favorites_keyboard(favorites: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура со списком избранных продуктов."""
    buttons = []
    
    if not favorites:
        buttons.append([InlineKeyboardButton("😕 Пока ничего нет", callback_data="food_noop")])
    else:
        for i, fav in enumerate(favorites[:10]):
            name = fav.get("food_name", "Неизвестный")[:25]
            weight = fav.get("amount_g", 0)
            kcal = fav.get("kcal", 0)
            
            # Добавляем кнопку изменения веса прямо в карточку
            buttons.append([
                InlineKeyboardButton(f"{name} ({weight}г, {kcal} ккал)", callback_data=f"food_fav_{i}"),
                InlineKeyboardButton("✏️ Вес", callback_data=f"food_fav_change_weight_{i}")
            ])
            
    buttons.append(get_back_keyboard("food_back_to_diary"))
    return InlineKeyboardMarkup(buttons)


def get_custom_weight_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ручного ввода веса."""
    # Цифровая клавиатура для удобства
    numbers = [
        ["1", "2", "3"],
        ["4", "5", "6"],
        ["7", "8", "9"],
        ["Clear", "0", "."],
    ]
    
    keyboard = []
    for row in numbers:
        keyboard.append([InlineKeyboardButton(n, callback_data=f"food_weight_num_{n}") for n in row])
        
    keyboard.append([
        InlineKeyboardButton("❌ Очистить", callback_data="food_weight_clear"),
        InlineKeyboardButton("✓ Использовать", callback_data="food_weight_use"),
    ])
    keyboard.append(get_back_keyboard("food_back_to_products"))
    
    return InlineKeyboardMarkup(keyboard)


def get_recent_foods_keyboard(recent_foods: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура с недавними блюдами."""
    buttons = []
    
    for i, food in enumerate(recent_foods[:8]):
        name = food.get("name", "Неизвестный")[:25]
        weight = food.get("weight", 100)
        calories = food.get("kcal", 0)
        
        buttons.append([InlineKeyboardButton(f"{name} ({weight}г)", callback_data=f"food_recent_{i}")])
        
    buttons.append(get_back_keyboard("food_select_method"))
    return InlineKeyboardMarkup(buttons)