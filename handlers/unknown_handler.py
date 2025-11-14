"""Обработчик неизвестных сообщений."""
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message

from handlers.states import TextConfirmation

router = Router(name="unknown_handler")


@router.message(F.text & ~F.text.startswith("/"), ~StateFilter(TextConfirmation.editing_text))
async def unknown_message(message: Message) -> None:
    """Обработчик неизвестных текстовых сообщений (исключает команды, фотографии и состояние редактирования)."""
    await message.answer(
        "🤔 Я не понимаю эту команду.\n\n"
        "📸 Отправьте мне фотографию списка продуктов, и я преобразую его в печатный вид!\n\n"
        "Используйте /help для получения справки."
    )

