import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ========== ВСТАВЬТЕ ВАШ ТОКЕН СЮДА ==========
TOKEN = os.GETENV("TELEGRAM_TOKEN")
# ============================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Главное меню (с кнопками Правила и Помощь) ---
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚶‍♀️ Создать прогулку")],
        [KeyboardButton(text="📅 Смотреть прогулки")],
        [KeyboardButton(text="👤 Мои прогулки")],
        [KeyboardButton(text="📖 Правила"), KeyboardButton(text="🆘 Помощь")]
    ],
    resize_keyboard=True
)

# --- Хранилище данных ---
walks = []          # Все прогулки
user_walks = {}     # На какие прогулки записан пользователь
user_walk_index = {} # Для листания прогулок
user_temp = {}      # Временные данные при создании

# --- Команда /start ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот «Рядом».\n\n"
        "🚶‍♀️ Создать прогулку — пригласить других\n"
        "📅 Смотреть прогулки — найти компанию\n"
        "👤 Мои прогулки — где вы участвуете\n"
        "📖 Правила — ознакомиться с правилами\n"
        "🆘 Помощь — связаться с поддержкой",
        reply_markup=main_kb
    )

# --- Правила ---
@dp.message(lambda m: m.text == "📖 Правила")
async def show_rules(message: types.Message):
    await message.answer(
        "📌 *Правила сообщества «Рядом»*\n\n"
        "1. Будьте вежливы друг с другом.\n"
        "2. Не опаздывайте без предупреждения.\n"
        "3. Если не можете прийти — предупредите организатора.\n"
        "4. О конфликтах пишите в поддержку: @ryadom_poisk_support_bot\n"
        "5. Соблюдайте личные границы.\n"
        "6. Запрещена реклама, алкоголь, наркотики.\n\n"
        "🌿 Хороших прогулок!",
        parse_mode="Markdown"
    )

# --- Помощь ---
@dp.message(lambda m: m.text == "🆘 Помощь")
async def show_help(message: types.Message):
    await message.answer(
        "🆘 *Если у вас возник вопрос*\n\n"
        "Напишите в поддержку:\n"
        "@ryadom_poisk_support_bot\n\n"
        "Мы ответим в ближайшее время.",
        parse_mode="Markdown"
    )

# --- СОЗДАНИЕ ПРОГУЛКИ ---
@dp.message(lambda m: m.text == "🚶‍♀️ Создать прогулку")
async def create_walk_start(message: types.Message):
    user_temp[message.from_user.id] = {"step": "name"}
    await message.answer(
        "🚶 Давайте создадим прогулку!\n\n"
        "Придумайте название (короткое и понятное).\n\n"
        "➤ Напишите название прогулки"
    )

@dp.message(lambda m: m.from_user.id in user_temp)
async def create_walk_collect(message: types.Message):
    user_id = message.from_user.id
    state = user_temp[user_id]
    step = state.get("step")

    if step == "name":
        state["name"] = message.text
        state["step"] = "place"
        await message.answer(
            "📍 Отлично!\n\n"
            "Где встретимся? Напишите конкретное место.\n\n"
            "➤ Укажите место сбора"
        )
    elif step == "place":
        state["place"] = message.text
        state["step"] = "datetime"
        await message.answer(
            "🕓 Теперь — когда гуляем?\n\n"
            "Напишите в формате: 15 мая, 18:30\n\n"
            "➤ Укажите дату и время"
        )
    elif step == "datetime":
        state["datetime"] = message.text
        state["step"] = "max_members"
        await message.answer(
            "👥 Сколько человек может пойти?\n\n"
            "• 0 — безлимит\n"
            "• Число — например, 5\n\n"
            "➤ Укажите максимум участников"
        )
    elif step == "max_members":
        state["max"] = message.text
        # Сохраняем прогулку
        new_walk = {
            "id": len(walks) + 1,
            "name": state["name"],
            "place": state["place"],
            "datetime": state["datetime"],
            "max": state["max"],
            "creator": user_id,
            "members": [user_id]
        }
        walks.append(new_walk)
        if user_id not in user_walks:
            user_walks[user_id] = []
        user_walks[user_id].append(new_walk["id"])
        del user_temp[user_id]
        await message.answer(
            "✅ Прогулка опубликована!\n\n"
            "Теперь её увидят другие участники.\n\n"
            "➤ Удачных вам встреч! 🌿",
            reply_markup=main_kb
        )

# --- СМОТРЕТЬ ПРОГУЛКИ (по одной, с кнопкой Дальше) ---
@dp.message(lambda m: m.text == "📅 Смотреть прогулки")
async def show_walks_start(message: types.Message):
    user_id = message.from_user.id
    
    # Показываем только прогулки, где есть места
    available_walks = []
    for walk in walks:
        max_members = int(walk["max"]) if walk["max"].isdigit() else 0
        if max_members == 0 or len(walk["members"]) < max_members:
            available_walks.append(walk)
    
    if not available_walks:
        await message.answer("Пока нет доступных прогулок. Создайте первую!")
        return
    
    user_walk_index[user_id] = {
        "walks": available_walks,
        "index": 0
    }
    await show_current_walk(message, user_id)

async def show_current_walk(message: types.Message, user_id: int):
    data = user_walk_index.get(user_id)
    if not data:
        return
    
    walks_list = data["walks"]
    current_idx = data["index"]
    
    if current_idx >= len(walks_list):
        await message.answer("Прогулки закончились.")
        del user_walk_index[user_id]
        return
    
    walk = walks_list[current_idx]
    
    current_members = len(walk["members"])
    max_members = int(walk["max"]) if walk["max"].isdigit() else 0
    members_text = f"{current_members}"
    if max_members > 0:
        members_text += f" / {max_members}"
    
    text = (
        f"📍 *{walk['name']}*\n"
        f"🗓 Когда: {walk['datetime']}\n"
        f"📍 Где: {walk['place']}\n"
        f"👥 Участников: {members_text}"
    )
    
    # Кнопки: Присоединиться, Дальше, Завершить
    keyboard_buttons = [
        [InlineKeyboardButton(text="✅ Присоединиться", callback_data=f"join_{walk['id']}")]
    ]
    if current_idx + 1 < len(walks_list):
        keyboard_buttons.append([InlineKeyboardButton(text="⏩ Дальше", callback_data="next_walk")])
    else:
        keyboard_buttons.append([InlineKeyboardButton(text="🏁 Завершить", callback_data="end_walks")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "next_walk")
async def next_walk(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = user_walk_index.get(user_id)
    
    if not data:
        await callback.answer("Список устарел. Нажмите «Смотреть прогулки» заново.")
        await callback.message.delete()
        return
    
    # Удаляем текущее сообщение
    await callback.message.delete()
    
    data["index"] += 1
    await show_current_walk(callback.message, user_id)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "end_walks")
async def end_walks(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id in user_walk_index:
        del user_walk_index[user_id]
    await callback.message.edit_text("🏁 Просмотр прогулок завершён.")
    await callback.answer()

# --- ПРИСОЕДИНИТЬСЯ К ПРОГУЛКЕ ---
@dp.callback_query(lambda c: c.data.startswith("join_"))
async def join_walk(callback: types.CallbackQuery):
    walk_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    # Находим прогулку
    walk = None
    for w in walks:
        if w["id"] == walk_id:
            walk = w
            break
    
    if not walk:
        await callback.answer("Прогулка не найдена!")
        return
    
    # Проверки
    if walk["creator"] == user_id:
        await callback.answer("❌ Вы создатель этой прогулки!")
        return
    
    if user_id in walk["members"]:
        await callback.answer("❌ Вы уже записаны на эту прогулку!")
        return
    
    max_members = int(walk["max"]) if walk["max"].isdigit() else 0
    if max_members > 0 and len(walk["members"]) >= max_members:
        await callback.answer("❌ Мест больше нет!")
        return
    
    # Добавляем участника
    walk["members"].append(user_id)
    
    if user_id not in user_walks:
        user_walks[user_id] = []
    if walk_id not in user_walks[user_id]:
        user_walks[user_id].append(walk_id)
    
    await callback.answer("✅ Вы записаны на прогулку!")
    
    # Обновляем сообщение
    current_members = len(walk["members"])
    members_text = f"{current_members}"
    if max_members > 0:
        members_text += f" / {max_members}"
    
    new_text = (
        f"📍 *{walk['name']}*\n"
        f"🗓 Когда: {walk['datetime']}\n"
        f"📍 Где: {walk['place']}\n"
        f"👥 Участников: {members_text}\n\n"
        f"✅ Вы записаны на прогулку!"
    )
    await callback.message.edit_text(new_text, parse_mode="Markdown", reply_markup=None)

# --- МОИ ПРОГУЛКИ ---
@dp.message(lambda m: m.text == "👤 Мои прогулки")
async def my_walks(message: types.Message):
    user_id = message.from_user.id
    
    # Собираем прогулки, где пользователь участник или создатель
    my_walks_list = []
    for walk in walks:
        if user_id in walk["members"] or walk["creator"] == user_id:
            my_walks_list.append(walk)
    
    if not my_walks_list:
        await message.answer("Вы пока не участвуете и не создали ни одной прогулки.")
        return
    
    for walk in my_walks_list:
        current_members = len(walk["members"])
        max_members = int(walk["max"]) if walk["max"].isdigit() else 0
        members_text = f"{current_members}"
        if max_members > 0:
            members_text += f" / {max_members}"
        
        creator_text = " (вы создатель)" if walk["creator"] == user_id else ""
        full_text = (
            f"📍 *{walk['name']}*{creator_text}\n"
            f"🗓 Когда: {walk['datetime']}\n"
            f"📍 Где: {walk['place']}\n"
            f"👥 Участников: {members_text}"
        )
        
        if walk["creator"] == user_id:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Удалить прогулку", callback_data=f"delete_{walk['id']}")]
            ])
            await message.answer(full_text, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await message.answer(full_text, parse_mode="Markdown")

# --- УДАЛИТЬ ПРОГУЛКУ ---
@dp.callback_query(lambda c: c.data.startswith("delete_"))
async def delete_walk(callback: types.CallbackQuery):
    walk_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    walk_to_delete = None
    for walk in walks:
        if walk["id"] == walk_id:
            walk_to_delete = walk
            break
    
    if not walk_to_delete:
        await callback.answer("Прогулка не найдена!")
        return
    
    if walk_to_delete["creator"] != user_id:
        await callback.answer("Вы можете удалять только свои прогулки!")
        return
    
    # Удаляем
    walks[:] = [walk for walk in walks if walk["id"] != walk_id]
    
    # Удаляем из user_walks
    for uid in user_walks:
        if walk_id in user_walks[uid]:
            user_walks[uid].remove(walk_id)
    
    await callback.answer("Прогулка удалена!")
    await callback.message.edit_text(callback.message.text + "\n\n❌ Прогулка удалена", reply_markup=None)

# --- ЗАПУСК БОТА ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

