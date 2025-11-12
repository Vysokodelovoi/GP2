import os, time, random, argparse
from datetime import datetime, timezone
import pandas as pd
from urllib.parse import urlparse, parse_qs

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service

SEARCH_URL = "https://eda.yandex.ru/search?filterSlug=search_restaurant&filterType=quickfilter&query=%D0%BF%D0%B8%D1%86%D1%86%D0%B0"

BROWSER_PATHS = ["/Applications/Yandex.app/Contents/MacOS/Yandex",]
CHROMEDRIVER_PATH = os.path.abspath("./chromedriver")
USER_DATA_DIR = os.path.abspath("user-data-selenium")

def find_browser():
    for p in BROWSER_PATHS:
        if os.path.exists(p):
            return p
    return None

def build_driver(binary_path):
    opts = webdriver.ChromeOptions()
    opts.binary_location = binary_path
    opts.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    opts.add_argument("--window-size=1280,2600")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
    svc = Service(CHROMEDRIVER_PATH)
    drv = webdriver.Chrome(service=svc, options=opts)
    drv.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"})

    return drv

def normalize_url(href: str):
    if not href: return ""
    href = href.split("#")[0]
    if "/r/" in href and "placeSlug=" in href:
        try:
            slug = parse_qs(urlparse(href).query).get("placeSlug", [None])[0]
            if slug:
                href = f"https://eda.yandex.ru/restaurant/{slug}"
        except Exception:
            pass
    if "/restaurant/" in href and "/preview" not in href:
        return href.split("?")[0]
    return ""

def collect_now(driver, seen: set):
    try:
        elems = driver.find_elements(By.CSS_SELECTOR, "a[href*='/restaurant/'], a[href*='/r/']")
        for e in elems:
            url = normalize_url(e.get_attribute("href") or "")
            if url:
                seen.add(url)
    except Exception:
        pass

def endless_scroll(driver, minutes=6):
    seen = set()
    body = driver.find_element(By.TAG_NAME, "body")
    end_at = time.time() + minutes * 60
    no_growth = 0
    prev_count = 0

    while time.time() < end_at:
        try:
            driver.execute_script(f"window.scrollBy(0, {random.randint(300, 600)});")
        except Exception:
            pass
        if random.random() < 0.25:
            try: body.send_keys(Keys.PAGE_DOWN)
            except: pass
        if random.random() < 0.03:
            try: body.send_keys(Keys.PAGE_UP)
            except: pass

        collect_now(driver, seen)

        if random.random() < 0.08:
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception:
                pass

        time.sleep(random.uniform(0.45, 0.9))

        if len(seen) == prev_count:
            no_growth += 1
            if no_growth >= 6:
                try:
                    driver.execute_script("window.scrollBy(0, -500);"); time.sleep(0.3)
                    driver.execute_script("window.scrollBy(0, 1100);"); time.sleep(0.4)
                except Exception:
                    pass
                no_growth = 0
        else:
            no_growth = 0
            prev_count = len(seen)

    return sorted(seen)


def run(out_csv):
    binary = find_browser()
    if not binary:
        print("Браузер не найден."); return
    driver = build_driver(binary)
    try:
        driver.get(SEARCH_URL)
        time.sleep(1.5)

        try:
            for xp in [
                "//button[contains(@class,'tag')][.//span[contains(., 'Рестораны')]]",
                "//span[contains(., 'Рестораны')]/ancestor::button",
                "//span[contains(., 'Рестораны')]/ancestor::a",
            ]:
                btns = driver.find_elements(By.XPATH, xp)
                if btns:
                    try: btns[0].click(); time.sleep(0.6)
                    except: pass
                    break
        except Exception:
            pass

        urls = endless_scroll(driver, minutes=3)   # время сколько этот блядский скрипт длится
        print(f"Собрано ссылок: {len(urls)}")

        rows = [{
            "name": u.rstrip('/').split('/')[-1].replace('_',' '),
            "url": u,
            "city": "moscow",
            "collected_at": datetime.now(timezone.utc).isoformat(timespec='seconds')
        } for u in urls]

        pd.DataFrame(rows).to_csv(out_csv, index=False)
        print(f"Готово: {len(rows)} → {out_csv}")
    finally:
        try: driver.quit()
        except Exception: pass

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    run(a.out)
