import requests
import pandas as pd
import time

API_KEY = "***"
CITY_ID = "4504222397630173"

organizations = {
    "papa_johns": "70000001046153222",
    "dodo_pizza": "70000001032901383",
    "zotman": "70000001041312678",
    "foodband": "70000001017852371"
}

all_data = []

for name, ORG_ID in organizations.items():
    print(f"\nСобираем {name.upper()}")
    all_branches = []
    page = 1
    page_size = 10

    while True:
        params = {
            "org_id": ORG_ID,
            "city_id": CITY_ID,
            "fields": "items.point,items.address,items.full_address_name",
            "page": page,
            "page_size": page_size,
            "key": API_KEY
        }

        response = requests.get("https://catalog.api.2gis.com/3.0/items", params=params)
        data = response.json()

        if "result" not in data:
            print("Ошибка в ответе API:", data)
            break

        result = data["result"]
        items = result.get("items", [])

        if not items:
            print(f"Страница {page} пуста, выход из цикла")
            break

        all_branches.extend(items)
        print(f"Страница {page}: получено {len(items)}, всего собрано {len(all_branches)}")

        if len(items) < page_size:
            print("Достигнута последняя страница")
            break

        page += 1
        time.sleep(0.3)

    for b in all_branches:
        all_data.append({
            "brand": name,
            "id": b.get("id"),
            "name": b.get("name"),
            "full_address": b.get("full_address_name"),
            "lat": b.get("point", {}).get("lat"),
            "lon": b.get("point", {}).get("lon")
        })

df = pd.DataFrame(all_data)
df.to_csv("pizza_networks_moscow.csv", index=False, encoding="utf-8-sig")

print(f"\nВ CSV записано {len(df)} строк (pizza_networks_moscow.csv)")
print(df.head())
