"""Универсальный сервис OCR с поддержкой Datalab и PaddleOCR."""
import asyncio
import logging
from io import BytesIO
from typing import Optional, Tuple

from config import OCR_PROVIDER, PADDLE_OCR_LANG, DATALAB_API_KEY
from services.datalab_service import DatalabService

logger = logging.getLogger(__name__)


class PaddleOCRService:
    """Локальный OCR на базе PaddleOCR."""

    def __init__(self, lang: str = "ru"):
        try:
            from paddleocr import PaddleOCR  # type: ignore
        except Exception as exc:  # pragma: no cover - зависимость опциональная
            logger.error(
                "Не удалось импортировать PaddleOCR. Установите paddleocr и paddlepaddle.",
                exc_info=True,
            )
            raise exc

        # Инициализация может быть долгой, поэтому делаем один раз
        self._ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
        self.lang = lang
        logger.info("PaddleOCR инициализирован с языком %s", lang)

    def _extract_sync(self, image_bytes: bytes) -> Optional[str]:
        """Синхронное извлечение текста для запуска в отдельном потоке."""
        try:
            from PIL import Image
            import numpy as np
        except Exception as exc:
            logger.error("Для PaddleOCR требуется Pillow и numpy.", exc_info=True)
            raise exc

        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        ocr_result = self._ocr.ocr(np.array(image), cls=True)

        lines: list[str] = []
        for page in ocr_result:
            for line in page:
                text = line[1][0]
                if text:
                    lines.append(text)

        return "\n".join(lines) if lines else None

    async def extract_text_from_image(
        self, image_bytes: bytes, filename: str = "image.jpg", is_pdf: bool = False
    ) -> Optional[str]:
        if is_pdf:
            # PaddleOCR не умеет читать PDF напрямую
            logger.warning("PaddleOCR не поддерживает PDF напрямую. Передайте изображения.")
            return None

        try:
            return await asyncio.to_thread(self._extract_sync, image_bytes)
        except Exception as exc:
            logger.error("Ошибка PaddleOCR при извлечении текста: %s", exc, exc_info=True)
            return None


class OCRService:
    """Выбор OCR движка на основе конфигурации."""

    def __init__(self):
        self.provider = OCR_PROVIDER
        self.datalab_service: Optional[DatalabService] = None
        self.paddle_service: Optional[PaddleOCRService] = None

        # Первичная инициализация
        init_ok, init_msg = self._switch_provider(self.provider)
        if not init_ok:
            logger.error("Не удалось инициализировать OCR провайдер: %s", init_msg)
        else:
            logger.info("Используется OCR провайдер: %s", self.provider)

    async def extract_text(
        self, image_bytes: bytes, filename: str = "image.jpg", is_pdf: bool = False
    ) -> Optional[str]:
        if self.provider == "paddle":
            if not self.paddle_service:
                logger.error("PaddleOCR не инициализирован.")
                return None
            return await self.paddle_service.extract_text_from_image(
                image_bytes, filename=filename, is_pdf=is_pdf
            )

        if not self.datalab_service:
            logger.error("DatalabService не инициализирован.")
            return None

        return await self.datalab_service.extract_text_from_image(
            image_bytes, filename=filename, is_pdf=is_pdf
        )

    async def set_provider(self, provider: str) -> Tuple[bool, str]:
        """Меняет провайдер OCR на лету."""
        return self._switch_provider(provider)

    def _switch_provider(self, provider: str) -> Tuple[bool, str]:
        provider = provider.lower()
        if provider not in {"datalab", "paddle"}:
            return False, "Допустимые значения: datalab или paddle"

        # Если провайдер не меняется, просто вернуть успех
        if provider == self.provider and (
            (provider == "paddle" and self.paddle_service)
            or (provider == "datalab" and self.datalab_service)
        ):
            return True, f"OCR уже установлен: {provider}"

        if provider == "paddle":
            try:
                self.paddle_service = PaddleOCRService(lang=PADDLE_OCR_LANG)
                self.datalab_service = None
                self.provider = provider
                return True, "Переключено на PaddleOCR"
            except Exception as exc:
                self.paddle_service = None
                logger.error("Ошибка при инициализации PaddleOCR: %s", exc, exc_info=True)
                return False, "Не удалось инициализировать PaddleOCR. Проверьте зависимости."

        # provider == "datalab"
        if not DATALAB_API_KEY:
            return False, "DATALAB_API_KEY не задан. Установите переменную окружения."

        try:
            self.datalab_service = DatalabService()
            self.paddle_service = None
            self.provider = provider
            return True, "Переключено на Datalab"
        except Exception as exc:
            self.datalab_service = None
            logger.error("Ошибка при инициализации Datalab: %s", exc, exc_info=True)
            return False, "Не удалось инициализировать Datalab."
