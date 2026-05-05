# utils/ocr.py
import pytesseract
from PIL import Image
import re
import io

def extract_screen_time(image_bytes):
    """
    Принимает байты изображения, возвращает суммарное распознанное количество минут экранного времени.
    Для простоты ищем числа, похожие на часы и минуты (например, '3h 45m').
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, config='--psm 6')
        # Ищем паттерны вида "Xh Ym" или "X hours Y minutes"
        hours_match = re.findall(r'(\d+)\s*h', text)
        minutes_match = re.findall(r'(\d+)\s*m', text)
        total_minutes = 0
        for h in hours_match:
            total_minutes += int(h) * 60
        for m in minutes_match:
            total_minutes += int(m)
        # Если нашли общее время в минутах напрямую (например, 'Screen Time: 120m')
        direct = re.findall(r'(\d+)\s*min', text)
        if direct and not hours_match and not minutes_match:
            total_minutes = sum(int(x) for x in direct)
        return total_minutes
    except Exception as e:
        print(f"OCR error: {e}")
        return 0