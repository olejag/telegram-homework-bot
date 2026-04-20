import json
from pathlib import Path
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile


TOKEN = "8364336026:AAG98jesPl2QOilOqUxJZ2nyQlagc7yoQkc"



bot = Bot(token=TOKEN)
dp = Dispatcher()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def load_json(filename):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


homeworks = load_json("homeworks.json")
theory_tasks = load_json("theory.json")
probnik_codes = load_json("probniks.json")
ALLOWED_USERS = set(load_json("allowed_users.json")["users"])

users = {}

def exam_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📗 ЕГЭ", callback_data="exam:ege")
    kb.button(text="📘 ОГЭ", callback_data="exam:oge")
    kb.adjust(1)
    return kb.as_markup()


def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS


def ensure_user(chat_id: int):
    if chat_id not in users:
        users[chat_id] = {
            "hw": None,
            "question_index": 0,
            "score": 0,
            "answers": [],
            "mode": "menu",
            "last_menu": "main",
            "last_bot_message_id": None,
            "history_message_ids": [],
            "user_message_ids": [],
            "exam": None,
        }


async def delete_message_safe(chat_id: int, message_id):
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass


async def delete_last_bot_message(chat_id: int):
    ensure_user(chat_id)
    last_message_id = users[chat_id].get("last_bot_message_id")
    if last_message_id:
        await delete_message_safe(chat_id, last_message_id)
        users[chat_id]["last_bot_message_id"] = None


async def send_and_store(chat_id: int, text: str, reply_markup=None):
    ensure_user(chat_id)

    old_message_id = users[chat_id].get("last_bot_message_id")

    msg = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    users[chat_id]["last_bot_message_id"] = msg.message_id

    if old_message_id and old_message_id != msg.message_id:
        await delete_message_safe(chat_id, old_message_id)

    return msg


async def send_history_message(chat_id: int, text: str, reply_markup=None):
    ensure_user(chat_id)
    msg = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    users[chat_id]["history_message_ids"].append(msg.message_id)
    return msg


async def clear_history_messages(chat_id: int):
    ensure_user(chat_id)

    for message_id in users[chat_id]["history_message_ids"]:
        try:
            await bot.delete_message(chat_id, message_id)
        except:
            pass

    users[chat_id]["history_message_ids"] = []


async def clear_user_messages(chat_id: int):
    ensure_user(chat_id)

    for message_id in users[chat_id]["user_message_ids"]:
        try:
            await bot.delete_message(chat_id, message_id)
        except:
            pass

    users[chat_id]["user_message_ids"] = []


async def clear_quiz_and_probnik_messages(chat_id: int):
    await clear_history_messages(chat_id)
    await clear_user_messages(chat_id)
    await delete_last_bot_message(chat_id)


async def delete_callback_message(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except:
        pass


def calculate_score(chat_id: int, hw_id: str, answers: list) -> int:
    exam = users[chat_id]["exam"]
    hw = homeworks[exam][hw_id]
    score = 0

    for i, user_answer in enumerate(answers):
        if i < len(hw["questions"]):
            correct_answer = hw["questions"][i]["answer"].strip().lower()
            if user_answer.strip().lower() == correct_answer:
                score += 1

    return score


def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📚 Выбрать ДЗ", callback_data="choose_hw")
    kb.button(text="📖 Теория", callback_data="theory_menu")
    kb.button(text="🧪 Пробники", callback_data="probnik")
    kb.button(text="📘 Как пользоваться", callback_data="help")
    kb.adjust(1)
    return kb.as_markup()


def homework_menu(chat_id: int, prefix: str, back_callback: str = "main_menu"):
    kb = InlineKeyboardBuilder()
    exam = users[chat_id]["exam"]

    for hw_id, hw_data in homeworks[exam].items():
        kb.button(text=hw_data["title"], callback_data=f"{prefix}:{hw_id}")

    kb.button(text="⬅️ Назад", callback_data=back_callback)
    kb.adjust(1)
    return kb.as_markup()

def back_kb_to_main():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


def theory_menu_kb(chat_id: int):
    kb = InlineKeyboardBuilder()
    exam = users[chat_id]["exam"]

    for t_id, t_data in theory_tasks[exam].items():
        kb.button(text=t_data["title"], callback_data=f"theory:{t_id}")

    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


def theory_back_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="theory_menu")
    kb.adjust(1)
    return kb.as_markup()


def quiz_back_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="quiz_back")
    kb.adjust(1)
    return kb.as_markup()


def probnik_back_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


async def send_question(chat_id: int):
    ensure_user(chat_id)
    user = users[chat_id]
    hw = homeworks[user["hw"]]
    index = user["question_index"]

    if index >= len(hw["questions"]):
        user["score"] = calculate_score(chat_id, user["hw"], user["answers"])
        await send_history_message(
            chat_id,
            f"Твой результат: правильно {user['score']}/{len(hw['questions'])}",
            reply_markup=main_menu()
        )
        users[chat_id]["mode"] = "menu"
        users[chat_id]["hw"] = None
        users[chat_id]["question_index"] = 0
        users[chat_id]["score"] = 0
        users[chat_id]["answers"] = []
        users[chat_id]["last_menu"] = "main"
        users[chat_id]["last_bot_message_id"] = None
        return

    question_text = hw["questions"][index]["question"]
    await send_history_message(
        chat_id,
        question_text,
        reply_markup=quiz_back_menu()
    )
    users[chat_id]["last_bot_message_id"] = None


@dp.message(CommandStart())
async def start_handler(message: Message):
    if not is_allowed(message.from_user.id):
        try:
            await message.delete()
        except:
            pass
        await bot.send_message(message.chat.id, f"Твой ID: {message.from_user.id}")
        return

    ensure_user(message.chat.id)
    await clear_quiz_and_probnik_messages(message.chat.id)

    users[message.chat.id].update({
        "hw": None,
        "question_index": 0,
        "score": 0,
        "answers": [],
        "mode": "menu",
        "last_menu": "main",
    })

    await send_and_store(
        message.chat.id,
        "Привет! Я бот для проверки домашнего задания😁\n\nВыбери экзамен:",
        reply_markup=exam_menu()
    )


    try:
        await message.delete()
    except:
        pass

@dp.callback_query(F.data.startswith("exam:"))
async def exam_choose_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    exam_type = callback.data.split(":")[1]
    users[chat_id]["exam"] = exam_type
    users[chat_id]["mode"] = "menu"
    users[chat_id]["last_menu"] = "main"

    exam_name = "ЕГЭ" if exam_type == "ege" else "ОГЭ"

    new_msg = await send_and_store(
        chat_id,
        f"Выбран экзамен: {exam_name}\n\nГлавное меню:",
        reply_markup=main_menu()
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()



@dp.callback_query(F.data == "probnik")
async def probnik_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    users[chat_id]["mode"] = "probnik"
    users[chat_id]["last_menu"] = "main"

    new_msg = await send_and_store(
        chat_id,
        "Введи код варианта:",
        reply_markup=probnik_back_menu()
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()

@dp.callback_query(F.data == "help")
async def help_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    users[chat_id]["mode"] = "menu"
    users[chat_id]["last_menu"] = "help"

    file = FSInputFile("data/guide.pdf")

    msg = await bot.send_document(
        chat_id=chat_id,
        document=file,
        caption="📘 Руководство по боту:"
    )

    users[chat_id]["history_message_ids"].append(msg.message_id)

    await send_history_message(
        chat_id,
        "❓ Остались вопросы?\nНапиши мне: @kob_ww"
    )

    new_msg = await send_and_store(
        chat_id,
        "Если что — нажми «Назад» 👇",
        reply_markup=back_kb_to_main()
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    users[chat_id]["mode"] = "menu"
    users[chat_id]["last_menu"] = "main"
    users[chat_id]["hw"] = None
    users[chat_id]["question_index"] = 0
    users[chat_id]["score"] = 0
    users[chat_id]["answers"] = []

    new_msg = await send_and_store(
        chat_id,
        "Главное меню:",
        reply_markup=main_menu()
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data == "choose_hw")
async def choose_hw_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    users[chat_id]["last_menu"] = "choose_hw"
    users[chat_id]["mode"] = "menu"

    new_msg = await send_and_store(
        chat_id,
        "Выбери нужное ДЗ:",
        reply_markup=homework_menu(chat_id, "start_hw", "main_menu")
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data == "theory_menu")
async def theory_menu_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    users[chat_id]["last_menu"] = "theory_menu"
    users[chat_id]["mode"] = "menu"

    new_msg = await send_and_store(
        chat_id,
        "Выбери задание:",
        reply_markup=theory_menu_kb(chat_id)
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data.startswith("theory:"))
async def theory_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    t_id = callback.data.split(":")[1]
    if t_id not in theory_tasks:
        await callback.answer("Такого задания нет", show_alert=True)
        return

    users[chat_id]["last_menu"] = "theory_view"
    users[chat_id]["mode"] = "menu"

    new_msg = await send_and_store(
        chat_id,
        theory_tasks[t_id]["text"],
        reply_markup=theory_back_menu()
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data.startswith("start_hw:"))
async def start_hw_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    hw_id = callback.data.split(":")[1]
    hw = homeworks[hw_id]

    users[chat_id].update({
        "hw": hw_id,
        "question_index": 0,
        "score": 0,
        "answers": [],
        "mode": "quiz",
        "last_menu": "choose_hw",
    })

    if hw.get("file_link"):
        await send_history_message(
            chat_id,
            f"📄 Ссылка на домашнюю работу:\n{hw['file_link']}"
        )

    await send_question(chat_id)
    await delete_callback_message(callback)
    await callback.answer()

@dp.callback_query(F.data == "quiz_back")
async def quiz_back_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)

    # Если пользователь не в режиме quiz — просто вернуть в главное меню
    if users[chat_id].get("mode") != "quiz":
        await clear_quiz_and_probnik_messages(chat_id)

        new_msg = await send_and_store(
            chat_id,
            "Главное меню:",
            reply_markup=main_menu()
        )

        if callback.message.message_id != new_msg.message_id:
            await delete_callback_message(callback)

        await callback.answer()
        return

    # Если пользователь в ДЗ — очищаем все сообщения этого ДЗ
    await clear_quiz_and_probnik_messages(chat_id)

    users[chat_id].update({
        "hw": None,
        "question_index": 0,
        "score": 0,
        "answers": [],
        "mode": "menu",
        "last_menu": "choose_hw",
    })

    new_msg = await send_and_store(
        chat_id,
        "Выбери нужное ДЗ:",
        reply_markup=homework_menu(chat_id, "start_hw", "main_menu")
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()





@dp.message()
async def answer_handler(message: Message):
    if message.text and message.text.startswith("/"):
        return

    if not is_allowed(message.from_user.id):
        return

    chat_id = message.chat.id
    ensure_user(chat_id)

    if not message.text:
        try:
            await message.delete()
        except:
            pass
        await send_and_store(chat_id, "Пожалуйста, отправь текстовый ответ.")
        return

    if users[chat_id].get("mode") == "probnik":
        code = message.text.strip()

        try:
            await message.delete()
        except:
            pass

        await delete_last_bot_message(chat_id)

        if code in probnik_codes:
            await send_history_message(
                chat_id,
                f"Вот твой вариант:\n{probnik_codes[code]}",
                reply_markup=probnik_back_menu()
            )
        else:
            await send_history_message(
                chat_id,
                "Неверный код❌",
                reply_markup=probnik_back_menu()
            )

        users[chat_id]["mode"] = "menu"
        users[chat_id]["last_bot_message_id"] = None
        return

    if users[chat_id].get("mode") != "quiz":
        try:
            await message.delete()
        except:
            pass
        await send_and_store(chat_id, "Ты по моему по кнопке не попал🤔(напиши /start)")
        return

    user = users[chat_id]
    exam = users[chat_id]["exam"]
    hw = homeworks[exam][user["hw"]]
    index = user["question_index"]

    users[chat_id]["user_message_ids"].append(message.message_id)

    user_answer = message.text.strip().lower()
    correct_answer = hw["questions"][index]["answer"].strip().lower()

    if len(user["answers"]) == index:
        user["answers"].append(user_answer)
    else:
        user["answers"][index] = user_answer

    user["score"] = calculate_score(user["hw"], user["answers"])

    if user_answer == correct_answer:
        await send_history_message(chat_id, "Верно!✅")
    else:
        await send_history_message(chat_id, "Неверно❌.")

    users[chat_id]["question_index"] += 1
    await send_question(chat_id)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
print(homeworks)
print(theory_tasks)