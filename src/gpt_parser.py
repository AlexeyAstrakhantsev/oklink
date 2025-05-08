import asyncio
from playwright.async_api import async_playwright

async def scrape_tooltips(url, attempts=1):
    results = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=True если не хочешь видеть окно
        page = await browser.new_page()

        for i in range(attempts):
            print(f"\n🔁 Попытка {i + 1} из {attempts}")
            await page.goto(url)
            await page.wait_for_selector('.index_innerClassName__6ivtc')

            address_elements = await page.query_selector_all('.index_innerClassName__6ivtc')
            print(f"🔍 Найдено {len(address_elements)} адресов")

            for el in address_elements:
                try:
                    await el.hover()
                    await page.wait_for_timeout(500)  # Подождать, пока tooltip появится

                    tooltip = await page.query_selector('.okui-tooltip')
                    if tooltip:
                        text = await tooltip.inner_text()
                        if text not in results:
                            results.add(text)
                            print(f"🟡 Tooltip:\n{text}\n{'-'*50}")
                except Exception as e:
                    print(f"⚠️ Ошибка: {e}")

        await browser.close()

    print(f"\n✅ Всего уникальных tooltip'ов: {len(results)}")

# Запустить
if __name__ == "__main__":
    asyncio.run(scrape_tooltips("https://www.oklink.com/ethereum/tx-list", attempts=1))
