"""Сервис для работы с Datalab API."""
import asyncio
import logging
from io import BytesIO
from typing import Optional

import aiohttp

from config import DATALAB_API_KEY, DATALAB_API_URL, MAX_POLLS, POLLING_INTERVAL

logger = logging.getLogger(__name__)


class DatalabService:
    """Сервис для извлечения текста из изображений через Datalab API."""

    def __init__(self):
        self.api_key = DATALAB_API_KEY
        self.api_url = DATALAB_API_URL
        self.headers = {"X-Api-Key": self.api_key}

    async def extract_text_from_image(
        self, image_bytes: bytes, filename: str = "image.jpg", is_pdf: bool = False
    ) -> Optional[str]:
        """
        Извлекает текст из изображения или PDF используя Datalab Marker API.

        Args:
            image_bytes: Байты изображения или PDF
            filename: Имя файла для загрузки
            is_pdf: True если это PDF файл, False если изображение

        Returns:
            Извлеченный текст в формате markdown или None в случае ошибки
        """
        try:
            # Отправляем изображение или PDF на обработку
            request_id = await self._submit_image(image_bytes, filename, is_pdf)
            if not request_id:
                return None

            # Ожидаем завершения обработки и получаем результат
            result = await self._poll_for_result(request_id)
            return result

        except Exception as e:
            logger.error(f"Ошибка при извлечении текста: {e}", exc_info=True)
            return None

    async def _submit_image(self, image_bytes: bytes, filename: str, is_pdf: bool = False) -> Optional[str]:
        """Отправляет изображение или PDF на обработку в Datalab API."""
        async with aiohttp.ClientSession() as session:
            # Подготавливаем данные для multipart/form-data
            data = aiohttp.FormData()
            content_type = "application/pdf" if is_pdf else "image/jpeg"
            data.add_field(
                "file",
                BytesIO(image_bytes),
                filename=filename,
                content_type=content_type,
            )
            # Параметры согласно документации Datalab API
            data.add_field("mode", "accurate")  # Режим точного распознавания
            data.add_field("force_ocr", "False")  # Принудительный OCR для рукописного текста
            data.add_field("format_lines", "False")  # Частичный OCR строк для лучшей точности
            data.add_field("paginate", "False")  # Добавление разделителей страниц
            data.add_field("output_format", "markdown")  # Формат вывода: json, markdown, html
            data.add_field("use_llm", "False")  # Использование LLM для максимальной точности
            data.add_field("strip_existing_ocr", "False")  # Не удалять существующий OCR
            data.add_field("disable_image_extraction", "False")  # Отключить извлечение изображений
            data.add_field("keep_page_header_in_output", "False")  # Сохранять заголовки страниц
            data.add_field("keep_page_footer_in_output", "False")  # Не сохранять футеры страниц

            try:
                async with session.post(
                    self.api_url, data=data, headers=self.headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            f"Ошибка при отправке изображения: {response.status} - {error_text}"
                        )
                        return None

                    result = await response.json()
                    if not result.get("success"):
                        logger.error(f"API вернул ошибку: {result.get('error')}")
                        return None

                    request_id = result.get("request_id")
                    logger.info(f"Изображение отправлено на обработку, request_id: {request_id}")
                    return request_id

            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети при отправке изображения: {e}")
                return None

    async def _poll_for_result(self, request_id: str) -> Optional[str]:
        """Ожидает завершения обработки и получает результат."""
        check_url = f"{self.api_url}/{request_id}"

        async with aiohttp.ClientSession() as session:
            for i in range(MAX_POLLS):
                try:
                    async with session.get(check_url, headers=self.headers) as response:
                        if response.status != 200:
                            logger.error(
                                f"Ошибка при проверке статуса: {response.status}"
                            )
                            await asyncio.sleep(POLLING_INTERVAL)
                            continue

                        data = await response.json()
                        status = data.get("status")

                        if status == "complete":
                            if data.get("success"):
                                markdown_text = data.get("markdown", "")
                                logger.info("Обработка завершена успешно")
                                return markdown_text
                            else:
                                error = data.get("error", "Неизвестная ошибка")
                                logger.error(f"Обработка завершилась с ошибкой: {error}")
                                return None

                        elif status == "failed":
                            error = data.get("error", "Неизвестная ошибка")
                            logger.error(f"Обработка провалилась: {error}")
                            return None

                        # Статус processing - продолжаем ждать
                        logger.debug(f"Обработка в процессе... (попытка {i + 1}/{MAX_POLLS})")
                        await asyncio.sleep(POLLING_INTERVAL)

                except aiohttp.ClientError as e:
                    logger.error(f"Ошибка сети при проверке статуса: {e}")
                    await asyncio.sleep(POLLING_INTERVAL)

            logger.error("Превышено максимальное количество попыток проверки статуса")
            return None

