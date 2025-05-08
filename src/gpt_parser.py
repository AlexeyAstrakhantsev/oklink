import asyncio
import re
from playwright.async_api import async_playwright
import logging
from db.models import Database, AddressRepository
import os
from dotenv import load_dotenv
import time

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('parser.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация базы данных
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT')
}

async def scrape_tooltips(url: str, attempts: int = 5):
    # Инициализация базы данных
    db = Database(DB_CONFIG)
    db.init_tables()
    address_repo = AddressRepository(db)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        while True:  # Бесконечный цикл
            try:
                logger.info("🔄 Начинаем новую итерацию сбора данных")
                await page.goto(url)
                await page.wait_for_load_state('networkidle')

                tooltips = set()  # Множество для уникальных tooltips
                for attempt in range(1, attempts + 1):
                    logger.info(f"🔁 Попытка {attempt} из {attempts}")
                    try:
                        address_elements = await page.query_selector_all(".index_innerClassName__6ivtc")
                        logger.info(f"🔍 Найдено {len(address_elements)} адресов")

                        for i in range(len(address_elements)):
                            try:
                                fresh_elements = await page.query_selector_all(".index_innerClassName__6ivtc")
                                if i >= len(fresh_elements):
                                    continue

                                element = fresh_elements[i]
                                
                                # Проверяем содержимое элемента
                                text = await element.inner_text()
                                text = text.strip()
                                
                                # Если текст начинается с 0x - пропускаем (это адрес)
                                if text.startswith('0x'):
                                    logger.debug(f"⏩ Пропускаем элемент только с адресом: {text}")
                                    continue
                                    
                                # Если есть дополнительный текст (имя) - делаем наведение
                                logger.info(f"🔄 Наведение на элемент с именем: {text}")
                                await element.hover()
                                await page.wait_for_timeout(300)  # Пауза для появления tooltip

                                tooltip_el = await page.query_selector(".index_title__9lx6D")
                                if tooltip_el:
                                    text = await tooltip_el.inner_text()
                                    tooltip_text = text.strip()
                                    logger.info(f"🟡 Tooltip: {tooltip_text}")
                                    tooltips.add(tooltip_text)

                            except Exception as e:
                                logger.error(f"⚠️ Ошибка при обработке элемента: {e}")

                        logger.info(f"✅ Всего уникальных tooltip'ов: {len(tooltips)}")
                        break

                    except Exception as e:
                        logger.error(f"⚠️ Ошибка при попытке {attempt}: {e}")
                        if attempt == attempts:
                            logger.error("❌ Не удалось собрать все tooltips после нескольких попыток")
                        await page.reload()
                        await page.wait_for_timeout(3000)

                # Обработка и сохранение tooltip'ов
                parsed_results = []
                for tooltip in tooltips:
                    match = re.match(r"(?P<type>\w+):\s+(?P<name>.+?)\s+(?P<address>0x[a-fA-F0-9]{40})", tooltip)
                    if match:
                        result = {
                            "type": match.group("type"),
                            "name": match.group("name"),
                            "address": match.group("address")
                        }
                        parsed_results.append(result)
                        
                        # Сохраняем в базу данных
                        try:
                            address_data = {
                                'address': result['address'],
                                'name': result['name'],
                                'tag': result['type']
                            }
                            address_repo.save_address(address_data)
                            logger.info(f"✅ Сохранен адрес: {result['address']} с именем: {result['name']} и тегом: {result['type']}")
                        except Exception as e:
                            logger.error(f"❌ Ошибка при сохранении адреса {result['address']}: {e}")

                logger.info(f"\n🔎 Распознано адресов с именами: {len(parsed_results)}")
                for item in parsed_results:
                    logger.info(f"🔹 Type: {item['type']}, Name: {item['name']}, Address: {item['address']}")

                # Пауза между итерациями (10 секунд)
                logger.info("💤 Пауза 10 секунд перед следующей итерацией...")
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"❌ Критическая ошибка в основном цикле: {e}")
                logger.info("💤 Пауза 5 секунд перед повторной попыткой...")
                await asyncio.sleep(5)

# Запуск скрипта
if __name__ == "__main__":
    asyncio.run(scrape_tooltips("https://www.oklink.com/ethereum/tx-list", attempts=3))
