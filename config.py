"""Конфигурация бота."""
import os
from typing import Optional

from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Telegram Bot Token (получить у @BotFather)
BOT_TOKEN: Optional[str] = os.getenv("BOT_TOKEN")

# OCR провайдер: datalab (по умолчанию) или paddle
OCR_PROVIDER: str = os.getenv("OCR_PROVIDER", "datalab").lower()
PADDLE_OCR_LANG: str = os.getenv("PADDLE_OCR_LANG", "ru")

# Datalab API Key (получить на https://datalab.to)
DATALAB_API_KEY: Optional[str] = os.getenv("DATALAB_API_KEY")

# Datalab API URL
DATALAB_API_URL: str = "https://www.datalab.to/api/v1/marker"

# Настройки для обработки изображений
IMAGE_MAX_SIZE: int = 10 * 1024 * 1024  # 10 MB
PDF_MAX_SIZE: int = 50 * 1024 * 1024  # 50 MB (PDF могут быть больше)
POLLING_INTERVAL: int = 2  # секунды между проверками статуса
MAX_POLLS: int = 300  # максимум попыток проверки статуса

# Проверка наличия обязательных переменных
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен. Установите переменную окружения BOT_TOKEN.")

if OCR_PROVIDER not in {"datalab", "paddle"}:
    raise ValueError("OCR_PROVIDER должен быть 'datalab' или 'paddle'.")

if OCR_PROVIDER == "datalab" and not DATALAB_API_KEY:
    raise ValueError("DATALAB_API_KEY не установлен. Установите переменную окружения DATALAB_API_KEY.")

