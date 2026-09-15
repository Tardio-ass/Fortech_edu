"""AI-слой: превращает фразу человека в фильтры и объясняет выдачу.

Две функции:
  parse_query()  — «хочу IT в Астане до 800к с грантом» -> Filters(...)
  explain()      — короткий текст под результатами

Важно: если ключа нет или Gemini упал, работает запасной разбор по правилам.
Демо на защите не должно падать из-за чужого сервера — это частая
причина провала на хакатонах.
"""

import json
import os
import re

import httpx

from .models import Filters, MatchedProgram

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

PARSE_PROMPT = """Ты разбираешь запрос абитуриента и возвращаешь ТОЛЬКО JSON без markdown.

Схема (все поля необязательны, отсутствующее ставь null или false):
{{
  "city": строка или null,
  "field": одно из ["IT","Экономика","Медицина","Инженерия","Право","Педагогика","Гуманитарные"] или null,
  "max_tuition_kzt": целое число в тенге или null,
  "grant_only": true/false,
  "dormitory_required": true/false,
  "military_department_required": true/false,
  "language": "казахский"/"русский"/"английский" или null,
  "max_duration_years": целое или null
}}

Правила:
- "800к", "800 тысяч" -> 800000; "1.5 млн" -> 1500000
- "грант", "бесплатно", "на грант" -> grant_only = true
- "общага", "общежитие" -> dormitory_required = true
- "военка", "военная кафедра" -> military_department_required = true

Запрос: {query}"""

EXPLAIN_PROMPT = """Ты помощник абитуриента. Кратко, 2-3 предложения, на русском,
объясни подборку. Опирайся ТОЛЬКО на данные ниже, ничего не выдумывай.
Не перечисляй всё подряд — скажи, почему эти варианты подходят под запрос.

Запрос: {query}
Найдено вариантов: {total}
Данные: {items}"""


async def _gemini(prompt: str, timeout: float = 12.0) -> str | None:
    """Один запрос к Gemini. Возвращает текст или None, если что-то пошло не так."""
    if not GEMINI_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                GEMINI_URL,
                params={"key": GEMINI_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:                       # noqa: BLE001
        print(f"[ai] Gemini недоступен: {exc}")
        return None


def parse_query_rules(query: str) -> Filters:
    """Запасной разбор без AI — простые правила по ключевым словам.

    Работает всегда. Хуже AI на сложных фразах, но демо не падает.
    """
    q = query.lower()
    f = Filters()

    # ключ — корень слова, чтобы ловились падежи: «в Астане», «из Алматы»
    cities = {
        "астан": "Астана",
        "алмат": "Алматы",
        "шымкент": "Шымкент",
        "караганд": "Караганда",
        "актобе": "Актобе",
        "костанай": "Костанай",
        "павлодар": "Павлодар",
        "тараз": "Тараз",
        "атырау": "Атырау",
        "семей": "Семей",
        "уральск": "Уральск",
        "усть-каменогорск": "Усть-Каменогорск",
    }
    for stem, name in cities.items():
        if stem in q:
            f.city = name
            break

    fields = {
        "IT": ["it", "айти", "программир", "информацион", "кибербез", "데이터", "данн"],
        "Экономика": ["эконом", "финанс", "бизнес", "менеджмент"],
        "Медицина": ["медиц", "врач", "стоматол"],
        "Инженерия": ["инженер", "строит", "нефт", "механик"],
        "Право": ["юрист", "прав", "юриспруд"],
    }
    for name, keys in fields.items():
        if any(k in q for k in keys):
            f.field = name
            break

    if any(w in q for w in ["грант", "бесплатн", "на грант"]):
        f.grant_only = True
    if any(w in q for w in ["общаг", "общежит"]):
        f.dormitory_required = True
    if any(w in q for w in ["военк", "военная кафедра"]):
        f.military_department_required = True

    # "до 800 тысяч", "800к", "1.5 млн"
    money = re.search(r"(\d+[.,]?\d*)\s*(к\b|тыс|млн|миллион)", q)
    if money:
        value = float(money.group(1).replace(",", "."))
        unit = money.group(2)
        f.max_tuition_kzt = int(value * (1_000_000 if unit.startswith(("млн", "миллион")) else 1_000))

    return f


async def parse_query(query: str) -> tuple[Filters, str]:
    """Основной разбор. Возвращает (фильтры, чем разобрали: 'ai' или 'rules')."""
    raw = await _gemini(PARSE_PROMPT.format(query=query))
    if raw:
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        try:
            return Filters(**json.loads(cleaned)), "ai"
        except Exception as exc:                   # noqa: BLE001
            print(f"[ai] ответ не разобрался как JSON: {exc}")

    return parse_query_rules(query), "rules"


async def explain(query: str, results: list[MatchedProgram]) -> str:
    """Короткий текст под выдачей. Без AI — простая фраза."""
    if not results:
        return "По таким условиям ничего не нашлось. Попробуй смягчить фильтры."

    items = [
        {
            "university": r.university_name,
            "city": r.city,
            "program": r.program.name,
            "tuition": r.program.tuition_per_year_kzt,
            "grant": r.program.grant_available,
        }
        for r in results[:5]
    ]
    text = await _gemini(
        EXPLAIN_PROMPT.format(query=query, total=len(results), items=json.dumps(items, ensure_ascii=False))
    )
    if text:
        return text.strip()

    return f"Нашлось вариантов: {len(results)}. Сверху — те, что ближе всего к твоим условиям."
