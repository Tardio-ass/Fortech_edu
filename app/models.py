"""Схемы данных. Всё, что ходит между фронтом и бэком, описано здесь.

Зачем: если формат описан в одном месте, FastAPI сам проверяет данные
и сам рисует документацию на /docs. Фронтендер смотрит /docs и не
спрашивает тебя, какие поля приходят.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Program(BaseModel):
    """Одна образовательная программа внутри университета."""

    code: str
    name: str
    field: str                      # IT, Экономика, Медицина ...
    degree: str = "бакалавр"
    duration_years: int = 4
    languages: list[str] = []
    tuition_per_year_kzt: int = 0
    grant_available: bool = False
    min_score_grant: int = 0
    min_score_paid: int = 0
    application_deadline: str | None = None


class University(BaseModel):
    """Университет с набором программ."""

    id: str
    name: str
    short_name: str = ""
    city: str
    ownership: Literal["государственный", "частный", "автономный"] = "государственный"
    website: str = ""
    has_dormitory: bool = False
    has_military_department: bool = False
    programs: list[Program] = []


class Filters(BaseModel):
    """Фильтры поиска.

    Это же — результат разбора запроса на естественном языке.
    AI получает фразу пользователя и возвращает ровно эту структуру.
    """

    city: str | None = None
    field: str | None = None
    max_tuition_kzt: int | None = None
    grant_only: bool = False
    dormitory_required: bool = False
    military_department_required: bool = False
    language: str | None = None
    max_duration_years: int | None = None


class SearchRequest(BaseModel):
    """Тело запроса на /api/search."""

    query: str = Field(..., examples=["хочу IT в Астане до 800 тысяч, нужен грант"])
    limit: int = 10


class MatchedProgram(BaseModel):
    """Программа, попавшая в выдачу, вместе с университетом."""

    university_id: str
    university_name: str
    city: str
    program: Program
    score: float                    # насколько подходит под запрос, 0..1


class SearchResponse(BaseModel):
    """Ответ поиска. Фронт рисует ровно это."""

    query: str
    filters: Filters                # что система поняла из запроса
    parsed_by: str                  # "ai" или "rules" — видно, сработал ли AI
    total: int
    results: list[MatchedProgram]
    explanation: str = ""           # текстовое объяснение выдачи
