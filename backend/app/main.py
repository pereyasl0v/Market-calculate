"""WB search backend. Internal search endpoint is NOT official Seller API."""
import os
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Market Calculate API", version="0.3.0")
origins = [v.strip() for v in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if v.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=["*"])

WB_BASE = "https://search.wb.ru"
WB_PATHS = ("/exactmatch/ru/common/v18/search", "/exactmatch/ru/common/v5/search")


class Product(BaseModel):
    position: int
    id: str
    name: str
    brand: str = ""
    price_rub: float | None = None
    basic_price_rub: float | None = None
    rating: float | None = None
    feedbacks: int | None = None


class SearchResponse(BaseModel):
    query: str
    source: str = "unofficial WB site search API"
    products: list[Product]
    total_returned: int
    warning: str = "Prices are from search JSON, NOT verified buyer-specific checkout prices or seller payouts."


def extract_products(payload: Any) -> list[Product]:
    if not isinstance(payload, dict):
        raise ValueError("WB payload is not an object")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    cards = data.get("products") or data.get("cards")
    if not isinstance(cards, list):
        raise ValueError("WB products array missing or schema changed")
    result = []
    for card in cards[:10]:
        if not isinstance(card, dict):
            continue
        sizes = card.get("sizes")
        price = {}
        if isinstance(sizes, list):
            for size in sizes:
                if isinstance(size, dict) and isinstance(size.get("price"), dict):
                    price = size["price"]
                    if price.get("product") is not None:
                        break
        # The known *U and sizes.price fields represent kopecks in observed schemas.
        raw_sale = price.get("product", card.get("salePriceU"))
        raw_basic = price.get("basic", card.get("priceU"))

        def rub(value: Any) -> float | None:
            try:
                number = float(value) / 100
                return round(number, 2) if number > 0 else None
            except (TypeError, ValueError):
                return None

        def maybe_int(value: Any) -> int | None:
            try:
                return int(value) if value is not None else None
            except (ValueError, TypeError):
                return None

        def maybe_float(value: Any) -> float | None:
            try:
                return float(value) if value is not None else None
            except (ValueError, TypeError):
                return None

        result.append(Product(
            position=len(result) + 1,
            id=str(card.get("id") or card.get("nmId") or ""),
            name=str(card.get("name") or "Без названия"),
            brand=str(card.get("brand") or ""),
            price_rub=rub(raw_sale),
            basic_price_rub=rub(raw_basic),
            rating=maybe_float(card.get("reviewRating", card.get("rating"))),
            feedbacks=maybe_int(card.get("feedbacks")),
        ))
    return result


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/wb/search", response_model=SearchResponse)
async def wb_search(
    query: str = Query(min_length=2, max_length=150),
    destination: int = Query(default=-1257786, description="WB destination code; region affects results"),
):
    params = {
        "appType": "1", "curr": "rub", "dest": str(destination),
        "lang": "ru", "page": "1", "query": query,
        "resultset": "catalog", "sort": "popular", "spp": "30",
    }
    errors = []
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(12.0), follow_redirects=False,
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; MarketCalculate/0.3)"},
    ) as client:
        for path in WB_PATHS:
            try:
                res = await client.get(f"{WB_BASE}{path}", params=params)
                res.raise_for_status()
                parsed = extract_products(res.json())
                if parsed and any(p.price_rub for p in parsed):
                    return SearchResponse(query=query, products=parsed, total_returned=len(parsed))
                errors.append(f"{path}: no usable prices")
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(f"{path}: {type(exc).__name__}")
    raise HTTPException(
        status_code=502,
        detail={"message": "WB search temporarily unavailable or payload changed", "attempts": errors},
    )
