"""Regression tests based on a *minimal, scrubbed* representation of HAR search JSON.

No original HAR, cookies, personal browser identifiers or large responses are committed.
"""
import asyncio

import httpx

from app.main import fetch_wb_top10, extract_products


def run_request(handler):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_wb_top10(client, "щипцы свп", 1259570991)
    return asyncio.run(run())


def test_live_har_root_products_schema_and_price_units():
    # Observed in user's HAR: /__internal/u-search/.../v18/search
    sample = {
        "metadata": {"name": "щипцы свп"},
        "products": [
            {"id": 542519138, "name": "Щипцы СВП", "sizes": [
                {"price": {"basic": 113600, "product": 35900, "wallet": 0}}
            ]},
            {"id": 175861775, "name": "Щипцы для плитки", "sizes": [
                {"price": {"basic": 78100, "product": 36700, "wallet": 0}}
            ]},
        ],
        "total": 1220,
    }
    cards = extract_products(sample)
    assert [c.id for c in cards] == ["542519138", "175861775"]
    assert cards[0].price_rub == 359
    assert cards[0].basic_price_rub == 1136
    assert cards[1].price_rub == 367
    # HTML snapshot separately showed 348 RUB and 355 RUB respectively.
    # We intentionally do not silently replace the JSON price with those values.


def test_primary_url_matches_har_and_preserves_top10_order():
    seen = []
    ids = [542519138, 175861775, 65580490, 277190782,
           467125747, 536036351, 208458264, 143282390,
           969312948, 42463424]

    def handler(request):
        seen.append(str(request.url))
        assert request.url.host == "www.wildberries.ru"
        assert request.url.path == "/__internal/u-search/exactmatch/ru/common/v18/search"
        assert request.url.params["query"] == "щипцы свп"
        assert request.url.params["dest"] == "1259570991"
        assert request.url.params["appType"] == "64"
        assert request.url.params["resultset"] == "catalog"
        assert request.url.params["sort"] == "popular"
        assert "page" not in request.url.params  # initial 100-product response, same order as HTML
        return httpx.Response(200, json={
            "products": [{"id": x, "name": "Карточка", "sizes": [{"price": {"product": 35900}}]}
                         for x in ids],
            "total": 1000,
        })

    cards, source = run_request(handler)
    assert len(seen) == 1
    assert source.startswith("https://www.wildberries.ru/__internal/u-search/")
    assert [p.id for p in cards] == [str(x) for x in ids]
    assert [p.position for p in cards] == list(range(1, 11))


def test_legacy_fallback_is_only_attempted_after_primary_failure():
    seen_hosts = []

    def handler(request):
        seen_hosts.append(request.url.host)
        if request.url.host == "www.wildberries.ru":
            return httpx.Response(403, json={"message": "Forbidden"})
        return httpx.Response(200, json={
            "products": [{"id": 1, "name": "Товар", "sizes": [{"price": {"product": 9900}}]}]
        })

    cards, source = run_request(handler)
    assert seen_hosts == ["www.wildberries.ru", "search.wb.ru"]
    assert cards[0].price_rub == 99
    assert source.startswith("https://search.wb.ru/")
