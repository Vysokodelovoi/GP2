import requests
import pandas as pd
import time

ACCESS_TOKEN = "vk1.a.WciHXwJkBtcR_Ilua3DXOTEOoR7XHZUa3KTvCKdxD5cN-C7ClOAftQYeWgMP3Nwaem9jmeqa3Ka8GdnX0-sBvngcSJTt9gx0NnYvfGzblMzbLfIHO37Cw_kzg8AGup8rB8-ig3LXJ5N5V4bRr3-pUelhXSo-v1bCe57_ER7T8NL6qTLgVyBqhZFExUvE4sk_usVm27NPoDjwQQ0X8hEMHQ"
OWNER_ID = -10095732
VERSION = "5.199"

def get_posts_batch(owner_id, offset=0, count=100):
    url = "https://api.vk.com/method/wall.get"
    params = {
        "owner_id": owner_id,
        "count": count,
        "offset": offset,
        "access_token": ACCESS_TOKEN,
        "v": VERSION
    }
    response = requests.get(url, params=params).json()
    if "response" in response:
        return response["response"]["items"]
    else:
        print("Ошибка:", response)
        return []

all_posts = []
batch_size = 100
total_needed = 1000

for offset in range(0, total_needed, batch_size):
    items = get_posts_batch(OWNER_ID, offset, batch_size)
    if not items:
        break
    all_posts.extend(items)
    print(f"Собрано {len(all_posts)} постов")
    time.sleep(0.35)

print(f"Всего собрано {len(all_posts)} постов")

posts = []
for item in all_posts:
    post_id = item["id"]
    likes = item["likes"]["count"]
    text = item.get("text", "").replace("\n", " ")
    date = pd.to_datetime(item["date"], unit="s")
    link = f"https://vk.com/wall{OWNER_ID}_{post_id}"

    posts.append({
        "post_id": post_id,
        "likes": likes,
        "text_preview": text,
        "date": date,
        "link": link
    })

df = pd.DataFrame(posts)
df = df.sort_values(by="likes", ascending=False).head(100)

df.to_csv("papa_johns_top100_posts.csv", index=False)
print("Сохранен файл papa_johns_top100_posts.csv")