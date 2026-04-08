import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = "8364336026:AAG98jesPl2QOilOqUxJZ2nyQlagc7yoQkc"

bot = Bot(token=TOKEN)
dp = Dispatcher()

homeworks = {
    "hw1": {
        "title": "Домашняя работа №1",
        "theory": "Теория для ДЗ №1:\nAddition basics.",
        "questions": [
            {"question": "Ответ на №1:", "answer": "1"},
            {"question": "Ответ на №2:", "answer": "1"},
            {"question": "Ответ на №3:", "answer": "1"},
        ],
    },
    "hw2": {
        "title": "Домашняя работа №2",
        "theory": "Теория для ДЗ №2:\nMultiplication basics.",
        "questions": [
            {"question": "Ответ на №1:", "answer": "1"},
            {"question": "Ответ на №2:", "answer": "1"},
            {"question": "Ответ на №3:", "answer": "1"},
        ],
    },
}

users = {}


def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📚 Выбрать ДЗ", callback_data="choose_hw")
    kb.button(text="📖 Теория", callback_data="theory_menu")
    kb.adjust(1)
    return kb.as_markup()


def homework_menu(prefix: str, back_callback: str = "main_menu"):
    kb = InlineKeyboardBuilder()
    for hw_id, hw_data in homeworks.items():
        kb.button(text=hw_data["title"], callback_data=f"{prefix}:{hw_id}")
    kb.button(text="⬅️ Назад", callback_data=back_callback)
    kb.adjust(1)
    return kb.as_markup()


def theory_back_menu(hw_id: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="theory_menu")
    kb.adjust(1)
    return kb.as_markup()


def quiz_back_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="quiz_back")
    kb.adjust(1)
    return kb.as_markup()


async def send_question(chat_id: int):
    user = users[chat_id]
    hw = homeworks[user["hw"]]
    index = user["question_index"]

    if index >= len(hw["questions"]):
        await bot.send_message(
            chat_id,
            f"Твой результат: правильно {user['score']}/{len(hw['questions'])}",
            reply_markup=main_menu()
        )
        users[chat_id]["mode"] = "menu"
        users[chat_id]["hw"] = None
        users[chat_id]["question_index"] = 0
        users[chat_id]["score"] = 0
        return

    question_text = hw["questions"][index]["question"]
    await bot.send_message(
        chat_id,
        question_text,
        reply_markup=quiz_back_menu()
    )


@dp.message(CommandStart())
async def start_handler(message: Message):
    users[message.chat.id] = {
        "hw": None,
        "question_index": 0,
        "score": 0,
        "mode": "menu",
        "last_menu": "main",
    }
    await message.answer(
        "Привет! Я бот для проверки домашнего задания😁",
        reply_markup=main_menu()
    )


@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id

    if chat_id not in users:
        users[chat_id] = {
            "hw": None,
            "question_index": 0,
            "score": 0,
            "mode": "menu",
            "last_menu": "main",
        }
    else:
        users[chat_id]["mode"] = "menu"
        users[chat_id]["last_menu"] = "main"

    await callback.message.answer(
        "Главное меню:",
        reply_markup=main_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "choose_hw")
async def choose_hw_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id not in users:
        users[chat_id] = {
            "hw": None,
            "question_index": 0,
            "score": 0,
            "mode": "menu",
            "last_menu": "choose_hw",
        }
    else:
        users[chat_id]["last_menu"] = "choose_hw"

    await callback.message.answer(
        "Выбери нужное ДЗ:",
        reply_markup=homework_menu("start_hw", "main_menu")
    )
    await callback.answer()


@dp.callback_query(F.data == "theory_menu")
async def theory_menu_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id not in users:
        users[chat_id] = {
            "hw": None,
            "question_index": 0,
            "score": 0,
            "mode": "menu",
            "last_menu": "theory_menu",
        }
    else:
        users[chat_id]["last_menu"] = "theory_menu"

    await callback.message.answer(
        "Выбери по какому ДЗ тебе нужна теория:",
        reply_markup=homework_menu("theory", "main_menu")
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("theory:"))
async def theory_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    hw_id = callback.data.split(":")[1]
    theory_text = homeworks[hw_id]["theory"]

    if chat_id not in users:
        users[chat_id] = {
            "hw": None,
            "question_index": 0,
            "score": 0,
            "mode": "menu",
            "last_menu": "theory_view",
        }
    else:
        users[chat_id]["last_menu"] = "theory_view"

    await callback.message.answer(
        theory_text,
        reply_markup=theory_back_menu(hw_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("start_hw:"))
async def start_hw_handler(callback: CallbackQuery):
    hw_id = callback.data.split(":")[1]

    users[callback.message.chat.id] = {
        "hw": hw_id,
        "question_index": 0,
        "score": 0,
        "mode": "quiz",
        "last_menu": "choose_hw",
    }

    await callback.message.answer(f"{homeworks[hw_id]['title']}")
    await send_question(callback.message.chat.id)
    await callback.answer()


@dp.callback_query(F.data == "quiz_back")
async def quiz_back_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id

    if chat_id not in users or users[chat_id].get("mode") != "quiz":
        await callback.message.answer(
            "Главное меню:",
            reply_markup=main_menu()
        )
        await callback.answer()
        return

    user = users[chat_id]

    if user["question_index"] > 0:
        user["question_index"] -= 1
        await callback.message.answer("Возвращаемся к предыдущему вопросу:")
        await send_question(chat_id)
    else:
        users[chat_id] = {
            "hw": None,
            "question_index": 0,
            "score": 0,
            "mode": "menu",
            "last_menu": "main",
        }
        await callback.message.answer(
            "Ты вернулся в главное меню:",
            reply_markup=main_menu()
        )

    await callback.answer()


@dp.message()
async def answer_handler(message: Message):
    chat_id = message.chat.id

    if chat_id not in users or users[chat_id].get("mode") != "quiz":
        await message.answer("Ты по моему по кнопке не попал🤔(напиши /start)")
        return

    if not message.text:
        await message.answer("Пожалуйста, отправь текстовый ответ.")
        return

    user = users[chat_id]
    hw = homeworks[user["hw"]]
    index = user["question_index"]

    user_answer = message.text.strip().lower()
    correct_answer = hw["questions"][index]["answer"].strip().lower()

    if user_answer == correct_answer:
        users[chat_id]["score"] += 1
        await message.answer("Верно!✅")
    else:
        await message.answer("Неверно.")

    users[chat_id]["question_index"] += 1
    await send_question(chat_id)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())