"""Состояния FSM для бота."""
from aiogram.fsm.state import State, StatesGroup


class TextConfirmation(StatesGroup):
    """Состояния для подтверждения и редактирования текста."""
    waiting_for_confirmation = State()  # Ожидание подтверждения или редактирования
    editing_text = State()  # Редактирование текста


class BackgroundUpload(StatesGroup):
    """Состояния для загрузки фонового изображения."""
    waiting_for_background = State()  # Ожидание загрузки фонового изображения
