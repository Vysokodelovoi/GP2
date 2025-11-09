from playwright.async_api import async_playwright
import random
import json
import os
import asyncio
import re
from playwright.async_api import ElementHandle
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from contextlib import asynccontextmanager
from datetime import datetime
from tqdm import tqdm
import pandas as pd
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'./logs/scraper_{datetime.now().strftime("%d-%m__%H:%M:%S")}.log', mode='w',
                            encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

STORAGE_STATE_IN = "storage_state_new.json"
STORAGE_STATE_OUT = "storage_state_new.json"


class BrowserConfig:
    def __init__(self):
        self._headless = True
        self._lock = asyncio.Lock()

    async def set_headless(self, value: bool):
        async with self._lock:
            self._headless = value

    async def get_headless(self) -> bool:
        async with self._lock:
            return self._headless


browser_config = BrowserConfig()


async def _get_ancestor_chain(el: ElementHandle, max_levels: int = 6):
    """Возвращает список предков (включая self) до max_levels уровней."""
    chain = []
    cur = el
    for _ in range(max_levels):
        if not cur:
            break
        chain.append(cur)
        parent = await cur.evaluate_handle("node => node.parentElement")
        if not parent:
            break
        try:
            parent_el = parent.as_element()
        except Exception:
            parent_el = None
        if not parent_el:
            break
        cur = parent_el
    return chain


PRICE_FULL_RE = re.compile(
    r'(\d[\d\s\u2009]*[.,]?\d*)\s*₽')  # \u2009 — узкий пробел, используется на мобильной странице
HAS_LETTERS_RE = re.compile(r'[A-Za-zА-Яа-яЁё]')


async def _find_best_price_text_from_element(price_el: ElementHandle):
    """
    Находит элемент с ценой (все где есть ₽)
    """
    try:
        chain = await _get_ancestor_chain(price_el, max_levels=8)
        best_match = None
        for anc in chain:
            txt = await anc.text_content() or ""
            matches = list(PRICE_FULL_RE.finditer(txt))
            if not matches:
                continue
            candidate = max((m.group(1) for m in matches), key=len)
            if HAS_LETTERS_RE.search(candidate) or '%' in candidate:
                continue
            if best_match is None or len(candidate) > len(best_match):
                best_match = candidate

        if best_match:
            return best_match.strip() + " ₽"
        own_text = await price_el.text_content() or ""
        m = PRICE_FULL_RE.search(own_text)
        if m:
            if not (HAS_LETTERS_RE.search(m.group(1)) or '%' in m.group(1)):
                return m.group(1).strip() + " ₽"
        idx = own_text.find("₽")
        if idx != -1:
            before = own_text[:idx].strip()
            if before and not (HAS_LETTERS_RE.search(before) or '%' in before):
                return before + " ₽"
    except Exception:
        pass
    return None


async def _extract_title_from_container(item_el: ElementHandle):
    """
    Ищет названия блюд в контейнере
    """
    try:
        btn = await item_el.query_selector("button[aria-label]")
        if btn:
            aria = await btn.get_attribute("aria-label")
            if aria and aria.strip():
                return aria.strip()
    except Exception:
        pass

    try:
        img = await item_el.query_selector("img[alt]")
        if img:
            alt = await img.get_attribute("alt")
            if alt and alt.strip():
                return alt.strip()
    except Exception:
        pass

    try:
        for sel in ["h1", "h2", "h3", "h4", "h5", "h6", "[role='heading']"]:
            node = await item_el.query_selector(sel)
            if node:
                txt = await node.text_content()
                if txt and txt.strip() and "₽" not in txt and "г" not in txt:
                    return txt.strip()
    except Exception:
        pass

    try:
        candidates = []
        all_nodes = await item_el.query_selector_all("*")
        for node in all_nodes:
            try:
                t = await node.text_content()
                if not t:
                    continue
                s = t.strip()
                if len(s) < 3:
                    continue
                if "₽" in s:
                    continue
                if re.search(r'\d[\d\s\u2009]*г\b', s):
                    continue
                candidates.append(s)
            except Exception:
                continue
        if candidates:
            best = max(candidates, key=len)
            return best
    except Exception:
        pass

    return None


async def _extract_weight_from_container(item_el: ElementHandle):
    """
    Ищет строку с весом
    """
    try:
        text = await item_el.text_content() or ""
        m = re.search(r'\d[\d\s\u2009]*г\b', text)
        if m:
            return m.group(0).strip()
    except Exception:
        pass
    return None


async def collect_visible_items(page, seen, menu):
    """Собирает позиции из меню, по мере прокрутки страницы"""
    logger.debug("Starting to collect visible items (snapshot).")
    try:
        locator = page.locator("text=/₽/")
        try:
            price_handles = await locator.element_handles()
        except Exception as e:
            logger.exception("Failed to obtain element handles for price locator: %s", e)
            return

        logger.debug("Snapshot contains %d price elements.", len(price_handles))

        for i, price_el_handle in enumerate(price_handles):
            try:
                if not price_el_handle:
                    continue

                price_text = await price_el_handle.text_content()
                if not price_text:
                    continue

                idx = price_text.find("₽")
                if idx == -1:
                    continue

                price = price_text[:idx].strip() + " ₽"

                try:
                    item_container_handle = await price_el_handle.evaluate_handle("""
                        el => {
                            let parent = el.parentElement;
                            while (parent && parent !== document.body) {
                                try {
                                    if (parent.querySelector && parent.querySelector('button[aria-label]')) return parent;
                                } catch(e) {}
                                parent = parent.parentElement;
                            }
                            return null;
                        }
                    """)
                except PlaywrightTimeoutError as e:
                    logger.debug("Timeout when evaluating parent for index %d: %s", i, e)
                    continue
                except Exception as e:
                    logger.debug("Error when evaluating parent for index %d: %s", i, e)
                    continue

                item_el = item_container_handle.as_element() if item_container_handle else None
                if not item_el:
                    try:
                        chain = await _get_ancestor_chain(price_el_handle, max_levels=4)
                        item_el = None
                        for anc in chain:
                            t = await anc.text_content()
                            if t and len(t.strip()) > 3:
                                item_el = anc
                                break
                    except Exception:
                        item_el = None

                if not item_el:
                    continue

                title = await _extract_title_from_container(item_el)
                if not title:
                    full = await item_el.text_content() or ""
                    idx2 = full.find("₽")
                    if idx2 != -1:
                        maybe = full[:idx2].strip()
                        if len(maybe) > 3:
                            title = maybe
                if not title:
                    continue
                title = title.strip()

                weight = await _extract_weight_from_container(item_el)

                key = f"{title}|{price}"
                if key in seen:
                    continue
                seen.add(key)
                menu.append({"title": title, "price": price, "weight": weight})

            except Exception as e:
                logger.exception("Exception processing snapshot item #%d: %s", i, e)
                continue

    except Exception as e:
        logger.exception("Error in collect_visible_items: %s", e)


async def parse_pizzeria(url):
    logger.debug(f"Starting parsing for URL: {url}")
    headless = await browser_config.get_headless()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, slow_mo=100)
        logger.debug("Browser launched.")

        iphone_13 = p.devices["iPhone 13 Pro"]
        context_args = iphone_13.copy()
        if os.path.exists(STORAGE_STATE_IN):
            try:
                with open(STORAGE_STATE_IN, 'r', encoding='utf-8') as f:
                    storage_state = json.load(f)
                context_args['storage_state'] = storage_state
                logger.info(f"Loaded state from {STORAGE_STATE_IN}")
            except Exception as e:
                logger.warning(f"Error loading cookies from {STORAGE_STATE_IN}: {e}")
        else:
            logger.info(f"File {STORAGE_STATE_IN} not found — starting without authorization")

        context = await browser.new_context(**context_args)
        logger.debug("New context created.")
        page = await context.new_page()
        logger.debug("New page created.")

        try:
            await page.goto(url, timeout=120000)
            logger.debug(f"Navigated to {url}")
            await page.wait_for_load_state("domcontentloaded")
            logger.debug("Page loaded (domcontentloaded)")
            await asyncio.sleep(3)
            logger.debug("Slept for 3 seconds after load.")

            # Название
            try:
                name = await page.text_content("h1")
                name = name.strip() if name else None
                logger.debug(f"Extracted name: {name}")
            except:
                name = None
                logger.debug("No name found.")
                return {
                    "name": None,
                    "reviews": None,
                    "delivery_info": None,
                    "Menu": None,
                }
            if name == "Подтвердите, что запросы отправляли вы, а не робот":
                await browser_config.set_headless(False)
            elif not headless:
                await browser_config.set_headless(True)

            try:
                rating = await page.locator("big").all_inner_texts()
                reviews = await page.locator("small").all_inner_texts()
                elem = page.locator("xpath=//div[contains(text(), 'Бесплатная доставка')]").first
                delivery_info = await elem.inner_text()
                rating = " ".join(rating)
                reviews = " ".join(reviews)
                logger.debug(f"Extracted rating: {rating}, reviews: {reviews}, delivery_info: {delivery_info}")
            except:
                rating = reviews = delivery_info = None
                logger.debug("No rating/reviews/delivery info found.")

            logger.info("Starting scroll and menu collection...")
            seen = set()
            menu = []
            stable_positions = []
            max_nochange = 10
            prev_seen_count = 0
            idle_iters = 0

            while True:
                logger.debug("Collecting visible items in loop.")
                await collect_visible_items(page, seen, menu)

                if len(seen) == prev_seen_count:
                    idle_iters += 1
                    logger.debug(f"No new items, idle_iters: {idle_iters}")
                else:
                    idle_iters = 0
                    logger.debug(f"New items found, resetting idle_iters to 0")

                prev_seen_count = len(seen)

                if idle_iters >= 6:
                    logger.info("No new elements appearing — stopping scroll.")
                    break

                y = await page.evaluate("window.scrollY")
                stable_positions.append(y)
                logger.debug(f"Current scrollY: {y}")

                if len(stable_positions) > max_nochange:
                    last = stable_positions[-max_nochange:]
                    if max(last) - min(last) < 10 and idle_iters >= 3:
                        logger.info("Seems reached end of page.")
                        break

                dy = random.randint(600, 1000)
                duration = random.randint(200, 900)
                logger.debug(f"Scrolling by dy={dy}, duration={duration}")
                await page.evaluate("""
                    (params) => {
                        const { dy, duration } = params;
                        const start = window.scrollY;
                        const end = start + dy;
                        let startTime = null;
                        function easeOutQuad(t) { return t * (2 - t); }
                        function animate(time) {
                            if (!startTime) startTime = time;
                            const progress = Math.min((time - startTime) / duration, 1);
                            const eased = easeOutQuad(progress);
                            window.scrollTo(0, start + (end - start) * eased);
                            if (progress < 1) requestAnimationFrame(animate);
                        }
                        requestAnimationFrame(animate);
                    }
                """, {"dy": dy, "duration": duration})
                await asyncio.sleep(random.uniform(0.9, 1.6))
                logger.debug("Slept after scroll.")

            logger.debug("Final collection of visible items.")
            await collect_visible_items(page, seen, menu)
            logger.info(f"Collected items: {len(menu)}")

            result = {
                "name": name,
                "reviews": f"{rating or '—'} ({reviews or '—'})",
                "delivery_info": delivery_info,
                "Menu": menu,
            }
            logger.debug(f"Result compiled: {result}")

        except Exception as e:
            logger.error(f"Error during parsing: {e}")
            result = None

        finally:
            try:
                storage_state = await context.storage_state()
                with open(STORAGE_STATE_OUT, "w", encoding="utf-8") as f:
                    json.dump(storage_state, f, ensure_ascii=False, indent=2)
                    logger.info(f"Cookies saved to {STORAGE_STATE_OUT}")
            except Exception as e:
                logger.error(f"Error saving cookies: {e}")

            await browser.close()
            logger.debug("Browser closed.")

    return result


async def main(urls):
    all_data = []
    try:
        for url in tqdm(urls):
            logger.debug(f"Processing URL in main: {url}")
            data = await parse_pizzeria(url)
            all_data.append(data)
            await asyncio.sleep(random.uniform(1, 4))
            logger.debug("Slept between parsings.")

    except Exception as e:
        logger.error(f'Exception occurred: {e}')
        logger.info(f'Checkpoint saved {all_data}')
        with open(f'./logs/checkpoint{datetime.now().strftime("%d-%m__%H:%M:%S")}.json', 'w', encoding='utf-8') as f:
            f.write(repr(all_data))

    with open("final_data.json", "w", encoding="utf-8") as f:
        f.write(repr(all_data))
    logger.info("All data saved to final_data.json")


if __name__ == "__main__":
    df = pd.read_csv('pizzerias.csv')
    urls = list(df.url)
    asyncio.run(main(urls))

    with open('urls.txt', 'w') as f:
        f.write(repr(urls))
