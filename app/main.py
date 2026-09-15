"""Точка входа. Здесь живут все HTTP-эндпоинты.

Запуск:  uvicorn app.main:app --reload
Документация: http://127.0.0.1:8000/docs  (генерируется сама, показать жюри!)
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import storage
from .ai import explain, parse_query
from .models import Filters, SearchRequest, SearchResponse, University
from .search import search

app = FastAPI(
    title="UniSearch API",
    description="Поиск университетов и программ по запросу на обычном языке",
    version="0.1.0",
)

# Без этого фронт на другом порту получит ошибку CORS и ничего не увидит.
# На хакатоне разрешаем всем; в проде тут был бы список доменов.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Живой ли сервер. Нужен для деплоя и для быстрой проверки фронтендером."""
    return {"status": "ok", **storage.stats()}


@app.get("/api/universities", response_model=list[University])
def list_universities(
    city: str | None = Query(None, description="Фильтр по городу"),
    field: str | None = Query(None, description="Фильтр по направлению"),
) -> list[University]:
    """Список университетов. Для страницы каталога на фронте."""
    result = storage.load_universities()
    if city:
        result = [u for u in result if city.lower() in u.city.lower()]
    if field:
        result = [
            u for u in result
            if any(field.lower() in p.field.lower() for p in u.programs)
        ]
    return result


@app.get("/api/universities/{university_id}", response_model=University)
def university_detail(university_id: str) -> University:
    """Карточка одного университета."""
    uni = storage.get_university(university_id)
    if not uni:
        raise HTTPException(status_code=404, detail="Университет не найден")
    return uni


@app.post("/api/search", response_model=SearchResponse)
async def smart_search(req: SearchRequest) -> SearchResponse:
    """Главный эндпоинт продукта.

    Три шага, которые ты называешь жюри:
      1. AI разбирает фразу человека в набор фильтров
      2. обычный поиск отбирает программы из нашей базы (без выдумок)
      3. AI объясняет, почему подобрал именно это
    """
    filters, parsed_by = await parse_query(req.query)
    results = search(filters, limit=req.limit)
    text = await explain(req.query, results)

    return SearchResponse(
        query=req.query,
        filters=filters,
        parsed_by=parsed_by,
        total=len(results),
        results=results,
        explanation=text,
    )


@app.post("/api/filter", response_model=SearchResponse)
async def filter_search(filters: Filters, limit: int = 10) -> SearchResponse:
    """Поиск по готовым фильтрам — для формы с чекбоксами на фронте."""
    results = search(filters, limit=limit)
    return SearchResponse(
        query="",
        filters=filters,
        parsed_by="manual",
        total=len(results),
        results=results,
    )


@app.post("/api/reload")
def reload_data() -> dict:
    """Перечитать data/universities.json без перезапуска сервера.

    Удобно: research залил новые данные — дёрнул этот эндпоинт, и всё обновилось.
    """
    storage.load_universities(force=True)
    return {"status": "reloaded", **storage.stats()}
