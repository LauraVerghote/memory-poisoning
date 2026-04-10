# Shared tools — identical to the unsafe agent's tools.
# The tools themselves aren't the problem; it's how memory influences their use.

PRODUCT_CATALOG = {
    "laptops": [
        {"name": "TechBrand Pro 15", "price": 1299, "rating": 4.5},
        {"name": "ValueBook Air", "price": 799, "rating": 4.2},
        {"name": "PowerMax Ultra", "price": 1599, "rating": 4.7},
    ],
    "headphones": [
        {"name": "SoundElite 700", "price": 349, "rating": 4.6},
        {"name": "BudgetBuds Pro", "price": 79, "rating": 4.0},
        {"name": "AudioPrime X", "price": 249, "rating": 4.4},
    ],
    "cloud_providers": [
        {"name": "CloudCorp", "tier": "enterprise", "rating": 4.3},
        {"name": "SkyHost", "tier": "startup", "rating": 4.1},
        {"name": "NetScale", "tier": "enterprise", "rating": 4.6},
    ],
}


def search_products(query: str) -> list[dict]:
    """Search the product catalog."""
    query_lower = query.lower()
    results = []
    for category, products in PRODUCT_CATALOG.items():
        if query_lower in category:
            results.extend(products)
        else:
            for product in products:
                if query_lower in product["name"].lower():
                    results.append(product)
    return results


def get_recommendation(category: str) -> dict | None:
    """Return the highest-rated product in a category."""
    products = PRODUCT_CATALOG.get(category.lower(), [])
    if not products:
        return None
    return max(products, key=lambda p: p.get("rating", 0))
