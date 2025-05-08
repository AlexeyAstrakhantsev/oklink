import asyncio
import re
from playwright.async_api import async_playwright

async def scrape_tooltips(url: str, attempts: int = 5):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url)

        tooltips = set()  # Множество для уникальных tooltips
        for attempt in range(1, attempts + 1):
            print(f"🔁 Попытка {attempt} из {attempts}")
            try:
                address_elements = await page.query_selector_all(".index_innerClassName__6ivtc")
                print(f"🔍 Найдено {len(address_elements)} адресов")

                for i in range(len(address_elements)):
                    try:
                        fresh_elements = await page.query_selector_all(".index_innerClassName__6ivtc")
                        if i >= len(fresh_elements):
                            continue

                        element = fresh_elements[i]
                        await element.hover()
                        await page.wait_for_timeout(300)  # Пауза для появления tooltip

                        tooltip_el = await page.query_selector(".index_title__9lx6D")
                        if tooltip_el:
                            text = await tooltip_el.inner_text()
                            tooltip_text = text.strip()
                            print(f"🟡 Tooltip: {tooltip_text}")
                            tooltips.add(tooltip_text)

                    except Exception as e:
                        print(f"⚠️ Ошибка при обработке элемента: {e}")

                print(f"✅ Всего уникальных tooltip'ов: {len(tooltips)}")
                break

            except Exception as e:
                print(f"⚠️ Ошибка при попытке {attempt}: {e}")
                if attempt == attempts:
                    print("❌ Не удалось собрать все tooltips после нескольких попыток")
                await page.reload()
                await page.wait_for_timeout(3000)

        await browser.close()

        # Обработка и разбор tooltip'ов
        parsed_results = []
        for tooltip in tooltips:
            match = re.match(r"(?P<type>\w+):\s+(?P<name>.+?)\s+(?P<address>0x[a-fA-F0-9]{40})", tooltip)
            if match:
                parsed_results.append({
                    "type": match.group("type"),
                    "name": match.group("name"),
                    "address": match.group("address")
                })

        print(f"\n🔎 Распознано адресов с именами: {len(parsed_results)}")
        for item in parsed_results:
            print(f"🔹 Type: {item['type']}, Name: {item['name']}, Address: {item['address']}")

# Запуск скрипта
asyncio.run(scrape_tooltips("https://www.oklink.com/ethereum/tx-list", attempts=3))
