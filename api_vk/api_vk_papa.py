import requests
import pandas as pd
import time

ACCESS_TOKEN = "***"
OWNER_ID = -10095732
VERSION = "5.199"

def vk_request(method, params):
    url = f"https://api.vk.com/method/{method}"
    params.update({"v": VERSION, "access_token": ACCESS_TOKEN})
    r = requests.get(url, params=params).json()
    if "response" in r:
        return r["response"]
    else:
        print("Ошибка:", r)
        return None

print("Загружаю посты со стены")
all_posts = []
offset = 0

while True:
    posts_data = vk_request("wall.get", {
        "owner_id": OWNER_ID,
        "count": 100,
        "offset": offset
    })
    if not posts_data or not posts_data["items"]:
        break

    all_posts.extend(posts_data["items"])
    offset += 100
    print(f"Загружено {len(all_posts)} постов")
    time.sleep(0.3)

    if len(all_posts) >= 500:
        break

posts = all_posts[:500]
print(f"Найдено {len(posts)} постов")

all_comments = []

for idx, post in enumerate(posts, 1):
    post_id = post["id"]
    print(f"[{idx}/{len(posts)}] Пост {post_id}")

    offset = 0
    while True:
        comments_data = vk_request("wall.getComments", {
            "owner_id": OWNER_ID,
            "post_id": post_id,
            "count": 100,
            "offset": offset,
            "sort": "asc",
            "preview_length": 0,
            "extended": 0
        })
        if not comments_data:
            break

        comments = comments_data["items"]
        if not comments:
            break

        for c in comments:
            all_comments.append({
                "post_id": post_id,
                "comment_id": c["id"],
                "user_id": c["from_id"],
                "date": c["date"],
                "text": c.get("text", "")
            })

        offset += 100
        time.sleep(0.3)

    print(f"Собрано {len([c for c in all_comments if c['post_id'] == post_id])} комментариев")

df = pd.DataFrame(all_comments)
print(f"Всего комментариев собрано: {len(df)}")
df.to_csv("vk_papajohns_full_comments.csv", index=False)
print("Сохранено в vk_papajohns_full_comments.csv")
