import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = "8364336026:AAEKd9jcRMgiHbWYQ6NH14B5BMiKsexSOW4"

bot = Bot(token=TOKEN)
dp = Dispatcher()
homeworks = {
    "hw1": {
        "title": "Homework 1",
        "theory": "Theory for Homework 1:\nAddition basics.",
        "questions": [
            {"answer": "4"},
            {"question": "3 + 5 = ?", "answer": "8"},
            {"question": "10 - 7 = ?", "answer": "3"},
        ],
    },
    "hw2": {
        "title": "Homework 2",
        "theory": "Theory for Homework 2:\nMultiplication basics.",
        "questions": [
            {"question": "2 * 3 = ?", "answer": "6"},
            {"question": "4 * 5 = ?", "answer": "20"},
        ],
    },
}

users = {}


def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="Choose Homework", callback_data="choose_hw")
    kb.button(text="Theory", callback_data="theory_menu")
    kb.adjust(1)
    return kb.as_markup()


def homework_menu(prefix: str):
    kb = InlineKeyboardBuilder()
    for hw_id, hw_data in homeworks.items():
        kb.button(text=hw_data["title"], callback_data=f"{prefix}:{hw_id}")
    kb.adjust(1)
    return kb.as_markup()


async def send_question(chat_id: int):
    user = users[chat_id]
    hw = homeworks[user["hw"]]
    index = user["question_index"]

    if index >= len(hw["questions"]):
        await bot.send_message(
            chat_id,
            f"Finished.\nYour result: {user['score']}/{len(hw['questions'])} correct."
        )
        users[chat_id]["mode"] = None
        return

    question_text = hw["questions"][index]["question"]
    await bot.send_message(chat_id, f"Question {index + 1}: {question_text}")


@dp.message(CommandStart())
async def start_handler(message: Message):
    users[message.chat.id] = {
        "hw": None,
        "question_index": 0,
        "score": 0,
        "mode": "menu",
    }
    await message.answer(
        "Hi. I am a homework checker bot.",
        reply_markup=main_menu()
    )


@dp.callback_query(F.data == "choose_hw")
async def choose_hw_handler(callback: CallbackQuery):
    await callback.message.answer(
        "Choose a homework:",
        reply_markup=homework_menu("start_hw")
    )
    await callback.answer()


@dp.callback_query(F.data == "theory_menu")
async def theory_menu_handler(callback: CallbackQuery):
    await callback.message.answer(
        "Choose homework theory:",
        reply_markup=homework_menu("theory")
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("theory:"))
async def theory_handler(callback: CallbackQuery):
    hw_id = callback.data.split(":")[1]
    theory_text = homeworks[hw_id]["theory"]
    await callback.message.answer(theory_text)
    await callback.answer()


@dp.callback_query(F.data.startswith("start_hw:"))
async def start_hw_handler(callback: CallbackQuery):
    hw_id = callback.data.split(":")[1]

    users[callback.message.chat.id] = {
        "hw": hw_id,
        "question_index": 0,
        "score": 0,
        "mode": "quiz",
    }

    await callback.message.answer(f"Starting {homeworks[hw_id]['title']}")
    await send_question(callback.message.chat.id)
    await callback.answer()


@dp.message()
async def answer_handler(message: Message):
    chat_id = message.chat.id

    if chat_id not in users or users[chat_id].get("mode") != "quiz":
        await message.answer("Press /start and choose homework first.")
        return

    user = users[chat_id]
    hw = homeworks[user["hw"]]
    index = user["question_index"]

    if index >= len(hw["questions"]):
        await message.answer("This homework is already finished.")
        return

    user_answer = message.text.strip().lower()
    correct_answer = hw["questions"][index]["answer"].strip().lower()

    if user_answer == correct_answer:
        users[chat_id]["score"] += 1
        await message.answer("Correct")
    else:
        await message.answer(
            f"Wrong. Correct answer: {hw['questions'][index]['answer']}"
        )

    users[chat_id]["question_index"] += 1
    await send_question(chat_id)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())