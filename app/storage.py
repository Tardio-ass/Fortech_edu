"""Загрузка базы университетов из JSON-файла.

Почему JSON, а не настоящая база: на хакатоне побеждает скорость.
JSON читается одной строкой, его правит research-человек прямо в редакторе,
и его можно залить в git. Если данных станет больше ~2000 программ —
переедем на SQLite, но для 72 часов этого не понадобится.
"""

import json
from pathlib import Path

from .models import University

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "universities.json"

_cache: list[University] | None = None


def load_universities(force: bool = False) -> list[University]:
    """Читает JSON и превращает его в объекты University.

    Результат кэшируется в памяти, чтобы не читать файл на каждый запрос.
    force=True перечитывает файл — удобно, когда research залил новые данные.
    """
    global _cache
    if _cache is not None and not force:
        return _cache

    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    universities: list[University] = []
    for item in raw:
        item.pop("_note", None)          # служебные поля из шаблона игнорируем
        universities.append(University(**item))

    _cache = universities
    return _cache


def get_university(university_id: str) -> University | None:
    """Один университет по id."""
    for uni in load_universities():
        if uni.id == university_id:
            return uni
    return None


def stats() -> dict:
    """Короткая статистика — пригодится на защите: «у нас N вузов, M программ»."""
    unis = load_universities()
    return {
        "universities": len(unis),
        "programs": sum(len(u.programs) for u in unis),
        "cities": sorted({u.city for u in unis}),
        "fields": sorted({p.field for u in unis for p in u.programs}),
    }
