import asyncio
from playwright.async_api import async_playwright

async def scrape_tooltips(url: str, attempts: int = 5):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # headless=True
        page = await browser.new_page()

        await page.goto(url)

        tooltips = set()  # Множество для уникальных tooltips
        for attempt in range(1, attempts + 1):
            print(f"🔁 Попытка {attempt} из {attempts}")
            try:
                # Получаем все адреса (или другие интересующие элементы)
                address_elements = await page.query_selector_all(".index_innerClassName__6ivtc")
                print(f"🔍 Найдено {len(address_elements)} адресов")

                # Проходим по каждому элементу
                for i in range(len(address_elements)):
                    try:
                        # Заново выбираем все элементы, чтобы избежать stale DOM references
                        fresh_elements = await page.query_selector_all(".index_innerClassName__6ivtc")
                        if i >= len(fresh_elements):
                            continue

                        element = fresh_elements[i]
                        await element.hover()
                        await page.wait_for_timeout(1000)  # увеличена задержка для появления tooltip

                        # Пытаемся найти tooltip, который может быть в другом элементе
                        tooltip_el = await page.query_selector(".okui-tooltip")
                        if tooltip_el:
                            text = await tooltip_el.inner_text()
                            print(f"🟡 Tooltip: {text}")
                            tooltips.add(text.strip())

                    except Exception as e:
                        print(f"⚠️ Ошибка при обработке элемента: {e}")
                
                print(f"✅ Всего уникальных tooltip'ов: {len(tooltips)}")
                break

            except Exception as e:
                print(f"⚠️ Ошибка при попытке {attempt}: {e}")
                if attempt == attempts:
                    print("❌ Не удалось собрать все tooltips после нескольких попыток")
                await page.reload()
                await page.wait_for_timeout(3000)  # Задержка после перезагрузки страницы

        await browser.close()

# Запуск скрипта
asyncio.run(scrape_tooltips("https://www.oklink.com/ethereum/tx-list", attempts=3))
