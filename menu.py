import json
from functools import lru_cache
from config import get_settings

@lru_cache()
def load_menu() -> dict:
    settings = get_settings()
    with open(settings.menu_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_menu_for_ai(language: str = "pt") -> str:
    menu = load_menu()
    lines = []
    lines.append(f"=== CARDÁPIO - {menu['restaurant']['name']} ===\n")
    for category in menu["categories"]:
        cat_name = category.get("name_pt", "")
        lines.append(f"\n[{cat_name.upper()}]")
        for item in category["items"]:
            name = item.get("name_pt", "")
            desc = item.get("description_pt", "")
            price = item["price"]
            lines.append(f"  - {name} (ID: {item['id']}): R$ {price:.2f} — {desc}")
    return "\n".join(lines)

def find_item_by_id(item_id: str) -> dict | None:
    menu = load_menu()
    for category in menu["categories"]:
        for item in category["items"]:
            if item["id"] == item_id:
                return item
    return None

def get_restaurant_info() -> dict:
    return load_menu()["restaurant"]
