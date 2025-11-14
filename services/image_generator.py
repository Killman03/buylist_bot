"""Сервис для генерации красивых изображений с текстом."""
import logging
from io import BytesIO
from typing import Optional, List

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class ImageGenerator:
    """Генератор изображений с текстом на красивом фоне."""

    def __init__(self):
        # Параметры изображения
        self.width = 1200
        self.min_height = 400
        self.padding = 60
        self.line_spacing = 20
        self.font_size = 48

        # Цвета (современная палитра)
        self.background_colors = [
            (250, 250, 255),  # Очень светло-голубой
            (255, 250, 250),  # Очень светло-розовый
            (250, 255, 250),  # Очень светло-зеленый
            (255, 255, 250),  # Очень светло-желтый
        ]
        self.text_color = (30, 30, 30)  # Темно-серый
        self.accent_color = (70, 130, 180)  # Стальной синий

    def create_image_with_text(self, text: str, background_image_bytes: Optional[bytes] = None) -> Optional[BytesIO]:
        """
        Создает изображение с текстом на красивом фоне.

        Args:
            text: Текст для отображения
            background_image_bytes: Байты фонового изображения (опционально)

        Returns:
            BytesIO объект с изображением в формате PNG
        """
        if not text or not text.strip():
            logger.warning("Пустой текст для генерации изображения")
            return None

        try:
            # Очищаем текст от лишних пробелов и форматируем
            cleaned_text = self._clean_text(text)

            # Пытаемся загрузить красивый шрифт
            font = self._get_font()

            # Создаем временное изображение для измерения текста
            temp_image = Image.new("RGB", (self.width, self.min_height), (255, 255, 255))
            temp_draw = ImageDraw.Draw(temp_image)

            # Разбиваем текст на строки с учетом ширины
            lines = self._wrap_text(temp_draw, cleaned_text, font, self.width - 2 * self.padding)

            # Вычисляем высоту изображения на основе количества строк
            line_height = self.font_size + self.line_spacing
            total_height = (
                len(lines) * line_height + 2 * self.padding + 40
            )  # +40 для заголовка

            # Создаем основное изображение
            if background_image_bytes:
                # Используем загруженное фоновое изображение
                try:
                    logger.info(f"Загрузка фонового изображения, размер: {len(background_image_bytes)} байт")
                    background_image = Image.open(BytesIO(background_image_bytes))
                    # Конвертируем в RGB если нужно
                    if background_image.mode != "RGB":
                        background_image = background_image.convert("RGB")
                    # Изменяем размер фона под нужные размеры
                    background_image = background_image.resize((self.width, total_height), Image.Resampling.LANCZOS)
                    image = background_image.copy()
                    logger.info(f"Фоновое изображение успешно применено, размер: {self.width}x{total_height}")
                except Exception as e:
                    logger.error(f"Не удалось загрузить фоновое изображение: {e}, используется цветной фон", exc_info=True)
                    import random
                    bg_color = random.choice(self.background_colors)
                    image = Image.new("RGB", (self.width, total_height), bg_color)
            else:
                # Используем цветной фон
                logger.info("Фоновое изображение не предоставлено, используется цветной фон")
                import random
                bg_color = random.choice(self.background_colors)
                image = Image.new("RGB", (self.width, total_height), bg_color)

            draw = ImageDraw.Draw(image)

            # Рисуем текст с выравниванием по левому краю
            y_position = self.padding + 30
            x_position = self.padding  # Левое выравнивание

            for line in lines:
                if not line.strip():  # Пустая строка
                    y_position += line_height
                    continue

                # Рисуем тень текста для лучшей читаемости
                shadow_offset = 2
                draw.text(
                    (x_position + shadow_offset, y_position + shadow_offset),
                    line,
                    font=font,
                    fill=(200, 200, 200, 100),
                )

                # Рисуем основной текст
                draw.text(
                    (x_position, y_position),
                    line,
                    font=font,
                    fill=self.text_color,
                )

                y_position += line_height

            # Сохраняем в BytesIO
            output = BytesIO()
            image.save(output, format="PNG", optimize=True)
            output.seek(0)

            logger.info(f"Изображение создано: {self.width}x{total_height}, строк: {len(lines)}")
            return output

        except Exception as e:
            logger.error(f"Ошибка при создании изображения: {e}", exc_info=True)
            return None

    def _clean_text(self, text: str) -> str:
        """Очищает и форматирует текст, сохраняя переносы строк."""
        # Разбиваем на строки и очищаем каждую
        lines = [line.strip() for line in text.split("\n")]
        # Удаляем пустые строки, но сохраняем структуру
        cleaned_lines = []
        for line in lines:
            if line:  # Если строка не пустая
                # Убираем множественные пробелы внутри строки
                while "  " in line:
                    line = line.replace("  ", " ")
                cleaned_lines.append(line)
        
        # Возвращаем текст с сохранением переносов строк
        return "\n".join(cleaned_lines)

    def _wrap_text(self, draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        """Разбивает текст на строки с учетом максимальной ширины и исходных переносов строк."""
        result_lines = []
        
        # Сначала разбиваем по исходным переносам строк
        original_lines = text.split("\n")
        
        for original_line in original_lines:
            if not original_line.strip():  # Пустая строка - добавляем как есть
                result_lines.append("")
                continue
            
            # Для каждой исходной строки делаем перенос по ширине
            words = original_line.split()
            current_line = []

            for word in words:
                # Проверяем, помещается ли слово в текущую строку
                test_line = " ".join(current_line + [word]) if current_line else word
                bbox = draw.textbbox((0, 0), test_line, font=font)
                text_width = bbox[2] - bbox[0]

                if text_width <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        result_lines.append(" ".join(current_line))
                    current_line = [word]

            # Добавляем последнюю строку для этого блока
            if current_line:
                result_lines.append(" ".join(current_line))

        return result_lines if result_lines else [text]

    def _get_font(self) -> ImageFont.FreeTypeFont:
        """Получает шрифт для текста."""
        try:
            # Пытаемся использовать системный шрифт
            # Для Windows
            try:
                font_path = "C:/Windows/Fonts/arial.ttf"
                return ImageFont.truetype(font_path, self.font_size)
            except:
                pass

            # Для Linux
            try:
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
                return ImageFont.truetype(font_path, self.font_size)
            except:
                pass

            # Для macOS
            try:
                font_path = "/System/Library/Fonts/Helvetica.ttc"
                return ImageFont.truetype(font_path, self.font_size)
            except:
                pass

            # Если не удалось найти системный шрифт, используем встроенный
            logger.warning("Не удалось загрузить системный шрифт, используется встроенный")
            return ImageFont.load_default()

        except Exception as e:
            logger.warning(f"Ошибка при загрузке шрифта: {e}, используется встроенный")
            return ImageFont.load_default()

