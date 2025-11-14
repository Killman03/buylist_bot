"""Обработчик для фотографий."""
import html
import logging
import re
from io import BytesIO

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, 
    BufferedInputFile, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery
)

from config import IMAGE_MAX_SIZE, PDF_MAX_SIZE
from services.datalab_service import DatalabService
from services.image_generator import ImageGenerator
from handlers.states import TextConfirmation, BackgroundUpload
from aiogram.filters import Command

logger = logging.getLogger(__name__)

router = Router(name="photo_handler")

# Инициализируем сервисы
datalab_service = DatalabService()
image_generator = ImageGenerator()

# Глобальное хранилище фоновых изображений пользователей (user_id -> image_bytes)
user_backgrounds: dict[int, bytes] = {}

# Поддерживаемые форматы изображений
IMAGE_MIME_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]

# Поддерживаемые форматы PDF
PDF_MIME_TYPES = ["application/pdf"]
PDF_EXTENSIONS = [".pdf"]


def escape_html_for_display(text: str) -> str:
    """
    Экранирует HTML-теги в тексте для безопасного отображения в Telegram.
    Удаляет HTML-теги и экранирует специальные символы.
    """
    # Удаляем HTML-теги
    text = re.sub(r'<[^>]+>', '', text)
    # Экранируем HTML-символы
    text = html.escape(text)
    return text


def create_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для подтверждения текста."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_text"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_text"),
        ],
        [
            InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_text"),
        ]
    ])
    return keyboard


async def show_text_for_confirmation(
    extracted_text: str, 
    message: Message, 
    processing_msg: Message,
    state: FSMContext
) -> None:
    """Показывает извлеченный текст пользователю для подтверждения."""
    # Сохраняем текст в состоянии
    await state.update_data(extracted_text=extracted_text)
    await state.set_state(TextConfirmation.waiting_for_confirmation)
    
    # Удаляем сообщение о обработке
    try:
        await processing_msg.delete()
    except Exception:
        pass
    
    # Ограничиваем длину текста для Telegram (максимум 4096 символов в сообщении)
    max_text_length = 3000  # Оставляем место для форматирования
    display_text = extracted_text[:max_text_length]
    is_truncated = len(extracted_text) > max_text_length
    
    # Экранируем HTML-теги для безопасного отображения
    display_text_escaped = escape_html_for_display(display_text)
    
    # Отправляем текст с кнопками
    text_message = (
        "📝 Извлеченный текст:\n\n"
        f"<code>{display_text_escaped}</code>\n\n"
        "Проверьте текст. Вы можете:\n"
        "• ✅ Подтвердить и создать изображение\n"
        "• ✏️ Редактировать текст\n"
        "• ❌ Отменить"
    )
    
    if is_truncated:
        text_message += f"\n\n⚠️ Текст обрезан (показано {max_text_length} из {len(extracted_text)} символов)"
    
    await message.answer(
        text_message,
        reply_markup=create_confirmation_keyboard()
    )


async def create_image_from_text(text: str, message: Message, state: FSMContext) -> None:
    """Создает изображение из текста и отправляет пользователю."""
    processing_msg = await message.answer("🎨 Создаю красивое изображение с текстом...")
    
    # Получаем фоновое изображение из глобального хранилища
    background_image_bytes = user_backgrounds.get(message.from_user.id)
    logger.info(f"Создание изображения для пользователя {message.from_user.id}, фон: {'есть' if background_image_bytes else 'нет'}")
    
    # Генерируем изображение с текстом
    result_image = image_generator.create_image_with_text(text, background_image_bytes)

    if not result_image:
        await processing_msg.edit_text("❌ Ошибка при создании изображения.")
        return

    # Отправляем результат
    result_image.seek(0)
    photo_file = BufferedInputFile(
        result_image.read(),
        filename="shopping_list.png"
    )

    await message.answer_photo(photo=photo_file)

    # Удаляем сообщение о обработке
    try:
        await processing_msg.delete()
    except Exception:
        pass


async def process_image(image_bytes: bytes, message: Message, processing_msg: Message, state: FSMContext) -> None:
    """Обрабатывает изображение: извлекает текст и показывает для подтверждения."""
    logger.info(f"Получено изображение от пользователя {message.from_user.id}, размер: {len(image_bytes)} байт")

    # Обновляем статус
    await processing_msg.edit_text("🔍 Извлекаю текст из изображения...")

    # Извлекаем текст через Datalab API
    extracted_text = await datalab_service.extract_text_from_image(
        image_bytes, filename=f"photo_{message.message_id}.jpg"
    )

    if not extracted_text or not extracted_text.strip():
        await processing_msg.edit_text(
            "❌ Не удалось извлечь текст из изображения. "
            "Попробуйте загрузить более четкое изображение с читаемым текстом."
        )
        return

    logger.info(f"Текст извлечен успешно, длина: {len(extracted_text)} символов")

    # Показываем текст для подтверждения
    await show_text_for_confirmation(extracted_text, message, processing_msg, state)


@router.message(Command("back"))
async def cmd_back(message: Message, state: FSMContext) -> None:
    """Обработчик команды /back для загрузки фонового изображения."""
    await state.set_state(BackgroundUpload.waiting_for_background)
    await message.answer(
        "🖼️ Отправьте изображение, которое будет использоваться как фон для списка продуктов.\n\n"
        "Изображение будет автоматически подогнано под размер текста."
    )


@router.message(StateFilter(BackgroundUpload.waiting_for_background), F.photo)
async def handle_background_photo(message: Message, state: FSMContext) -> None:
    """Обрабатывает загруженное фоновое изображение."""
    try:
        # Получаем файл фотографии (берем самое большое качество)
        photo = message.photo[-1]

        # Проверяем размер файла
        if photo.file_size and photo.file_size > IMAGE_MAX_SIZE:
            await message.answer(
                f"❌ Файл слишком большой. Максимальный размер: {IMAGE_MAX_SIZE / 1024 / 1024:.1f} MB"
            )
            return

        # Скачиваем файл
        file = await message.bot.get_file(photo.file_id)
        file_bytes = BytesIO()
        await message.bot.download_file(file.file_path, file_bytes)
        file_bytes.seek(0)
        image_bytes = file_bytes.read()

        # Сохраняем фоновое изображение для пользователя
        user_backgrounds[message.from_user.id] = image_bytes
        await state.clear()

        await message.answer("✅ Фоновое изображение сохранено! Теперь оно будет использоваться при создании списков продуктов.")
        logger.info(f"Пользователь {message.from_user.id} загрузил фоновое изображение, размер: {len(image_bytes)} байт")

    except Exception as e:
        logger.error(f"Ошибка при обработке фонового изображения: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обработке изображения. Попробуйте позже.")
        await state.clear()


@router.message(StateFilter(BackgroundUpload.waiting_for_background))
async def handle_background_invalid(message: Message) -> None:
    """Обрабатывает некорректный ввод при ожидании фонового изображения."""
    await message.answer("⚠️ Пожалуйста, отправьте изображение. Используйте команду /back для начала загрузки фона.")


@router.callback_query(F.data == "confirm_text", StateFilter(TextConfirmation.waiting_for_confirmation))
async def confirm_text_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик подтверждения текста."""
    data = await state.get_data()
    extracted_text = data.get("extracted_text", "")
    
    if not extracted_text:
        await callback.answer("❌ Ошибка: текст не найден", show_alert=True)
        await state.clear()
        return
    
    # Удаляем сообщение с кнопками
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    # Создаем изображение
    await create_image_from_text(extracted_text, callback.message, state)
    
    await state.clear()
    await callback.answer("✅ Изображение создано!")
    logger.info(f"Пользователь {callback.from_user.id} подтвердил текст и получил изображение")


@router.callback_query(F.data == "edit_text", StateFilter(TextConfirmation.waiting_for_confirmation))
async def edit_text_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик начала редактирования текста."""
    data = await state.get_data()
    extracted_text = data.get("extracted_text", "")
    
    if not extracted_text:
        await callback.answer("❌ Ошибка: текст не найден", show_alert=True)
        await state.clear()
        return
    
    # Переходим в режим редактирования
    await state.set_state(TextConfirmation.editing_text)
    
    # Ограничиваем длину для отображения
    max_text_length = 3000
    display_text = extracted_text[:max_text_length]
    is_truncated = len(extracted_text) > max_text_length
    
    # Экранируем HTML-теги для безопасного отображения
    display_text_escaped = escape_html_for_display(display_text)
    
    # Редактируем сообщение с инструкциями
    edit_message = (
        f"✏️ Редактирование текста:\n\n"
        f"<code>{display_text_escaped}</code>\n\n"
        "Отправьте исправленный текст. Или используйте кнопки:"
    )
    
    if is_truncated:
        edit_message += f"\n\n⚠️ Текст обрезан (показано {max_text_length} из {len(extracted_text)} символов)"
    
    await callback.message.edit_text(
        edit_message,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="↩️ Вернуться", callback_data="back_to_confirmation"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_text"),
            ]
        ])
    )
    
    await callback.answer()


@router.callback_query(F.data == "back_to_confirmation", StateFilter(TextConfirmation.editing_text))
async def back_to_confirmation_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат к подтверждению текста."""
    data = await state.get_data()
    extracted_text = data.get("extracted_text", "")
    
    await state.set_state(TextConfirmation.waiting_for_confirmation)
    
    max_text_length = 3000
    display_text = extracted_text[:max_text_length]
    is_truncated = len(extracted_text) > max_text_length
    
    # Экранируем HTML-теги для безопасного отображения
    display_text_escaped = escape_html_for_display(display_text)
    
    text_message = (
        "📝 Извлеченный текст:\n\n"
        f"<code>{display_text_escaped}</code>\n\n"
        "Проверьте текст. Вы можете:\n"
        "• ✅ Подтвердить и создать изображение\n"
        "• ✏️ Редактировать текст\n"
        "• ❌ Отменить"
    )
    
    if is_truncated:
        text_message += f"\n\n⚠️ Текст обрезан (показано {max_text_length} из {len(extracted_text)} символов)"
    
    await callback.message.edit_text(
        text_message,
        reply_markup=create_confirmation_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_text")
async def cancel_text_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик отмены."""
    await state.clear()
    try:
        await callback.message.edit_text("❌ Обработка отменена. Отправьте новое изображение или PDF.")
    except Exception:
        await callback.message.answer("❌ Обработка отменена. Отправьте новое изображение или PDF.")
    await callback.answer("Обработка отменена")


@router.message(StateFilter(TextConfirmation.editing_text), F.text)
async def process_edited_text(message: Message, state: FSMContext) -> None:
    """Обрабатывает отредактированный текст."""
    edited_text = message.text.strip()
    
    if not edited_text:
        await message.answer("❌ Текст не может быть пустым. Попробуйте еще раз.")
        return
    
    # Сохраняем отредактированный текст
    await state.update_data(extracted_text=edited_text)
    await state.set_state(TextConfirmation.waiting_for_confirmation)
    
    # Показываем отредактированный текст для подтверждения
    max_text_length = 3000
    display_text = edited_text[:max_text_length]
    is_truncated = len(edited_text) > max_text_length
    
    # Экранируем HTML-теги для безопасного отображения
    display_text_escaped = escape_html_for_display(display_text)
    
    text_message = (
        "📝 Отредактированный текст:\n\n"
        f"<code>{display_text_escaped}</code>\n\n"
        "Проверьте текст. Вы можете:\n"
        "• ✅ Подтвердить и создать изображение\n"
        "• ✏️ Редактировать текст\n"
        "• ❌ Отменить"
    )
    
    if is_truncated:
        text_message += f"\n\n⚠️ Текст обрезан (показано {max_text_length} из {len(edited_text)} символов)"
    
    await message.answer(
        text_message,
        reply_markup=create_confirmation_keyboard()
    )
    
    logger.info(f"Пользователь {message.from_user.id} отредактировал текст")


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext) -> None:
    """Обрабатывает загруженные фотографии."""
    # Проверяем, не находится ли пользователь в процессе редактирования или загрузки фона
    current_state = await state.get_state()
    if current_state:
        # Если пользователь загружает фон, не обрабатываем это как обычное фото
        # Обработчик с StateFilter(BackgroundUpload.waiting_for_background) обработает это
        if str(current_state) == str(BackgroundUpload.waiting_for_background):
            return  # Пусть обработчик фона обработает это
        await message.answer("⚠️ Завершите текущую операцию (подтвердите или отмените) перед отправкой нового файла.")
        return
    
    processing_msg = None
    try:
        # Отправляем сообщение о начале обработки
        processing_msg = await message.answer("📸 Получено изображение. Обрабатываю...")

        # Получаем файл фотографии (берем самое большое качество)
        photo = message.photo[-1]

        # Проверяем размер файла
        if photo.file_size and photo.file_size > IMAGE_MAX_SIZE:
            await processing_msg.edit_text(
                f"❌ Файл слишком большой. Максимальный размер: {IMAGE_MAX_SIZE / 1024 / 1024:.1f} MB"
            )
            return

        # Скачиваем файл
        file = await message.bot.get_file(photo.file_id)
        file_bytes = BytesIO()
        await message.bot.download_file(file.file_path, file_bytes)
        file_bytes.seek(0)
        image_bytes = file_bytes.read()

        # Обрабатываем изображение
        await process_image(image_bytes, message, processing_msg, state)

    except Exception as e:
        logger.error(f"Ошибка при обработке фотографии: {e}", exc_info=True)
        error_message = "❌ Произошла ошибка при обработке изображения. Попробуйте позже."
        try:
            if processing_msg:
                await processing_msg.edit_text(error_message)
            else:
                await message.answer(error_message)
        except Exception:
            try:
                await message.answer(error_message)
            except Exception:
                logger.error("Не удалось отправить сообщение об ошибке пользователю")
        finally:
            await state.clear()


@router.message(F.document)
async def handle_document(message: Message, state: FSMContext) -> None:
    """Обрабатывает документы (изображения и PDF, отправленные как файлы)."""
    # Проверяем, не находится ли пользователь в процессе редактирования
    current_state = await state.get_state()
    if current_state:
        await message.answer("⚠️ Завершите текущую операцию (подтвердите или отмените) перед отправкой нового файла.")
        return
    
    processing_msg = None
    try:
        document = message.document
        
        if not document:
            return
            
        mime_type = document.mime_type or ""
        file_name = (document.file_name or "").lower()
        
        # Проверяем, является ли документ изображением
        is_image = (
            mime_type in IMAGE_MIME_TYPES or
            any(file_name.endswith(ext) for ext in IMAGE_EXTENSIONS)
        )
        
        # Проверяем, является ли документ PDF
        is_pdf = (
            mime_type in PDF_MIME_TYPES or
            any(file_name.endswith(ext) for ext in PDF_EXTENSIONS)
        )
        
        if not is_image and not is_pdf:
            # Не поддерживаемый формат, пропускаем
            return
        
        # Определяем максимальный размер и сообщение
        max_size = PDF_MAX_SIZE if is_pdf else IMAGE_MAX_SIZE
        file_type = "PDF" if is_pdf else "изображение"
        
        # Отправляем сообщение о начале обработки
        processing_msg = await message.answer(f"📄 Получен {file_type}. Обрабатываю...")

        # Проверяем размер файла
        if document.file_size and document.file_size > max_size:
            await processing_msg.edit_text(
                f"❌ Файл слишком большой. Максимальный размер: {max_size / 1024 / 1024:.1f} MB"
            )
            return

        # Скачиваем файл
        file = await message.bot.get_file(document.file_id)
        file_bytes = BytesIO()
        await message.bot.download_file(file.file_path, file_bytes)
        file_bytes.seek(0)
        file_bytes_data = file_bytes.read()

        # Обрабатываем файл
        if is_pdf:
            await process_pdf(file_bytes_data, message, processing_msg, file_name, state)
        else:
            await process_image(file_bytes_data, message, processing_msg, state)

    except Exception as e:
        logger.error(f"Ошибка при обработке документа: {e}", exc_info=True)
        error_message = "❌ Произошла ошибка при обработке файла. Попробуйте позже."
        try:
            if processing_msg:
                await processing_msg.edit_text(error_message)
            else:
                await message.answer(error_message)
        except Exception:
            try:
                await message.answer(error_message)
            except Exception:
                logger.error("Не удалось отправить сообщение об ошибке пользователю")
        finally:
            await state.clear()


async def process_pdf(pdf_bytes: bytes, message: Message, processing_msg: Message, filename: str, state: FSMContext) -> None:
    """Обрабатывает PDF: извлекает текст и показывает для подтверждения."""
    logger.info(f"Получен PDF от пользователя {message.from_user.id}, размер: {len(pdf_bytes)} байт")

    # Обновляем статус
    await processing_msg.edit_text("🔍 Извлекаю текст из PDF...")

    # Извлекаем текст через Datalab API
    extracted_text = await datalab_service.extract_text_from_image(
        pdf_bytes, filename=filename, is_pdf=True
    )

    if not extracted_text or not extracted_text.strip():
        await processing_msg.edit_text(
            "❌ Не удалось извлечь текст из PDF. "
            "Попробуйте загрузить PDF с читаемым текстом."
        )
        return

    logger.info(f"Текст извлечен успешно, длина: {len(extracted_text)} символов")

    # Показываем текст для подтверждения
    await show_text_for_confirmation(extracted_text, message, processing_msg, state)
