"""Поиск по базе.

Ключевая идея проекта, её же говоришь жюри:
AI НЕ придумывает университеты. AI только переводит фразу человека
в фильтры. Сам отбор делает обычный детерминированный код по нашей базе.
Поэтому сервис не галлюцинирует: любая цифра в выдаче взята из данных.
"""

from .models import Filters, MatchedProgram, Program, University
from .storage import load_universities


def _matches(uni: University, prog: Program, f: Filters) -> bool:
    """Жёсткие условия: если хоть одно не выполнено — программа не показывается."""
    if f.city and f.city.lower() not in uni.city.lower():
        return False
    if f.field and f.field.lower() not in prog.field.lower():
        return False
    if f.max_tuition_kzt and prog.tuition_per_year_kzt > f.max_tuition_kzt > 0:
        return False
    if f.grant_only and not prog.grant_available:
        return False
    if f.dormitory_required and not uni.has_dormitory:
        return False
    if f.military_department_required and not uni.has_military_department:
        return False
    if f.language and not any(f.language.lower() in lng.lower() for lng in prog.languages):
        return False
    if f.max_duration_years and prog.duration_years > f.max_duration_years:
        return False
    return True


def _score(uni: University, prog: Program, f: Filters) -> float:
    """Мягкая оценка: чем лучше подходит, тем выше в выдаче.

    Начинаем с 0.5 и добавляем баллы за приятные совпадения.
    Это простая и объяснимая формула — на защите её легко защитить,
    в отличие от «чёрного ящика».
    """
    score = 0.5
    if f.grant_only and prog.grant_available:
        score += 0.2
    if f.max_tuition_kzt and 0 < prog.tuition_per_year_kzt <= f.max_tuition_kzt * 0.8:
        score += 0.15                      # заметно дешевле бюджета — это плюс
    if f.city and f.city.lower() in uni.city.lower():
        score += 0.1
    if uni.has_dormitory:
        score += 0.05
    return min(score, 1.0)


def search(f: Filters, limit: int = 10) -> list[MatchedProgram]:
    """Прогоняет все программы через фильтры и сортирует по релевантности."""
    found: list[MatchedProgram] = []

    for uni in load_universities():
        for prog in uni.programs:
            if not _matches(uni, prog, f):
                continue
            found.append(
                MatchedProgram(
                    university_id=uni.id,
                    university_name=uni.name,
                    city=uni.city,
                    program=prog,
                    score=_score(uni, prog, f),
                )
            )

    found.sort(key=lambda m: m.score, reverse=True)
    return found[:limit]
