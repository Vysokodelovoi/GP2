import requests
import pandas as pd
import time
import sys

ACCESS_TOKEN = "***"
OWNER_ID = -132401106
VERSION = "5.199"


def vk(method, **params):
    url = f"https://api.vk.com/method/{method}"
    params.update({"access_token": ACCESS_TOKEN, "v": VERSION})
    try:
        r = requests.get(url, params=params, timeout=30).json()
    except Exception as e:
        raise RuntimeError(f"HTTP error calling {method}: {e}")
    if "error" in r:
        code = r["error"].get("error_code")
        msg = r["error"].get("error_msg")
        raise RuntimeError(f"VK API error {code}: {msg}")
    return r["response"]


def get_posts(owner_id: int, limit: int = 1000):
    items = []
    offset = 0
    while offset < limit:
        try:
            resp = vk("wall.get", owner_id=owner_id, count=100, offset=offset)
        except RuntimeError as e:
            raise
        batch = resp.get("items", [])
        if not batch:
            break
        items.extend(batch)
        offset += 100
        print(f" Загружено постов: {len(items)}")
        time.sleep(0.33)
    return items[:limit]


def main():
    try:
        posts = get_posts(OWNER_ID, limit=1000)
    except RuntimeError as e:
        msg = str(e)
        if "15" in msg:
            print(
                " Access denied (error 15): стену можно читать только участникам сообщества или токен не имеет прав.")
        elif "5" in msg:
            print(" Auth error (error 5): проблема с токеном.")
        else:
            print(f" Ошибка при вызове VK API: {e}")
        sys.exit(1)
    if not posts:
        print(" Постов не получено. Возможно, стена пустая или недоступна для этого токена.")
        sys.exit(0)
    rows = []
    for p in posts:
        post_id = p.get("id")
        likes = p.get("likes", {}).get("count", 0)
        comments = p.get("comments", {}).get("count", 0)
        reposts = p.get("reposts", {}).get("count", 0)
        text = (p.get("text") or "").replace("\n", " ").strip()
        date = pd.to_datetime(p.get("date"), unit="s")
        post_link = f"https://vk.com/wall{OWNER_ID}_{post_id}"
        rows.append({
            "post_id": post_id,
            "likes": likes,
            "comments_count": comments,
            "reposts_count": reposts,
            "date": date,
            "text_preview": text[:400],  
            "post_link": post_link
        })
    df = pd.DataFrame(rows)
    df = df.sort_values("likes", ascending=False).head(100)
    out_file = "dodomsk_top100_posts.csv"
    df.to_csv(out_file, index=False)
    print(f" Готово! Сохранён файл: {out_file} ({len(df)} строк)")


if __name__ == "__main__":
    main()
