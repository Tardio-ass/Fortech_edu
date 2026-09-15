"""Пакет приложения.

Подхватываем .env здесь, до импорта остальных модулей, — тогда
os.getenv("GEMINI_API_KEY") в ai.py уже видит ключ.
"""

from dotenv import load_dotenv

load_dotenv()
