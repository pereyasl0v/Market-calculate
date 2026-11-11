from app.main import extract_products


def test_extract_products_prices_in_kopecks():
    data = {"data": {"products": [
        {"id": 123, "name": "Органайзер", "brand": "Test", "sizes": [{"price": {"basic": 120000, "product": 95000}}]},
        {"id": 456, "name": "Коробка", "salePriceU": 50000, "priceU": 80000},
    ]}}
    items = extract_products(data)
    assert len(items) == 2
    assert items[0].price_rub == 950
    assert items[0].basic_price_rub == 1200
    assert items[1].price_rub == 500


def test_missing_products_rejected():
    try:
        extract_products({"data": {}})
    except ValueError:
        return
    raise AssertionError("schema change must not silently return fake data")
