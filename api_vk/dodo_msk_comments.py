import requests
import pandas as pd
import time
import sys

ACCESS_TOKEN = "***"
OWNER_ID = -132401106

def vk(method, **params):
    url = f"https://api.vk.com/method/{method}"
    params.update({"access_token": ACCESS_TOKEN, "v": VERSION})
    r = requests.get(url, params=params, timeout=30).json()
    if "error" in r:
        code = r["error"]["error_code"]
        msg  = r["error"]["error_msg"]
        raise RuntimeError(f"VK API error {code}: {msg} | params={params}")
    return r["response"]

def check_token():
    try:
        me = vk("users.get")
        return True, me[0]["id"]
    except Exception as e:
        print(f" Токен не работает: {e}")
        return False, None

def get_posts(owner_id, limit=500):
    posts = []
    offset = 0
    while offset < limit:
        try:
            resp = vk("wall.get", owner_id=owner_id, count=100, offset=offset)
        except RuntimeError as e:
            print(f"wall.get ошибка на offset={offset}: {e}")
            break

        items = resp.get("items", [])
        if not items:
            break

        posts.extend(items)
        offset += 100
        print(f"Загружено {len(posts)} постов...")
        time.sleep(0.33)

    return posts[:limit]

def get_comments(owner_id, post_id):
    out = []
    offset = 0
    while True:
        try:
            resp = vk(
                "wall.getComments",
                owner_id=owner_id,
                post_id=post_id,
                count=100,
                offset=offset,
                sort="asc",
                preview_length=0,
                extended=0
            )
        except RuntimeError as e:
            print(f" comments ошибка (post {post_id}, offset {offset}): {e}")
            break

        items = resp.get("items", [])
        if not items:
            break

        for c in items:
            out.append({
                "post_id": post_id,
                "comment_id": c["id"],
                "user_id": c.get("from_id"),
                "date": pd.to_datetime(c["date"], unit="s"),
                "text": c.get("text", "")
            })

        offset += 100
        time.sleep(0.33)

    return out

def main():
    ok, uid = check_token()
    if not ok:
        sys.exit(1)

    print(f"OWNER_ID = {OWNER_ID}")

    posts = get_posts(OWNER_ID, limit=500)
    print(f"Всего постов: {len(posts)}")

    if not posts:
        print("Постов не получено. Скорее всего стена закрыта (error 15) "
              "или токен без прав wall/groups.")
        return

    all_comments = []
    for i, p in enumerate(posts, 1):
        pid = p["id"]
        print(f"[{i}/{len(posts)}] post {pid}")
        all_comments.extend(get_comments(OWNER_ID, pid))

    df = pd.DataFrame(all_comments)
    print(f"Всего комментариев: {len(df)}")

    df.to_csv("vk_group_132401106_comments.csv", index=False)
    print("Сохранено: vk_group_132401106_comments.csv")

if __name__ == "__main__":
    main()