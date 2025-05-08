from playwright.sync_api import sync_playwright
import time
import logging
import json
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_addresses():
    addresses = {}
    with sync_playwright() as p:
        # Запускаем браузер в headless режиме
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        page = browser.new_page()
        
        try:
            # Загружаем страницу
            logger.info("Загрузка страницы...")
            page.goto("https://www.oklink.com/ethereum/tx-list")
            logger.info("Страница загружена")
            
            # Ждем загрузки таблицы
            logger.info("Ожидание загрузки таблицы...")
            page.wait_for_selector('.okui-table-row')
            logger.info("Таблица загружена")
            
            # Даем время на загрузку динамического контента
            time.sleep(2)
            
            # Получаем все строки с адресами
            address_blocks = page.query_selector_all('.index_wrapper__ns7tB')
            logger.info(f"Найдено блоков с адресами: {len(address_blocks)}")
            
            # Обрабатываем каждый блок
            for i, block in enumerate(address_blocks, 1):
                try:
                    # Получаем ссылку с адресом
                    link = block.query_selector('a.index_link__gPnZX')
                    if link:
                        # Получаем адрес из href
                        href = link.get_attribute('href')
                        address = href.split('/')[-1]
                        
                        # Получаем имя из span
                        name_span = link.query_selector('span.oklink-ignore-locale')
                        name = name_span.get_attribute('data-original') if name_span else None
                        
                        # Выводим отладочную информацию
                        logger.info(f"Обработка блока {i}:")
                        logger.info(f"  href: {href}")
                        logger.info(f"  address: {address}")
                        logger.info(f"  name: {name}")
                        
                        if address and name:
                            addresses[address] = name
                            print(f"\nАдрес: {address}")
                            print(f"Имя: {name}")
                            print("-" * 50)
                        else:
                            logger.info("  Пропуск: нет адреса или имени")
                except Exception as e:
                    logger.error(f"Ошибка при обработке блока {i}: {e}")
                    continue
            
            # Выводим итоговую статистику
            print(f"\nВсего найдено уникальных адресов: {len(addresses)}")
            
            # Сохраняем HTML для отладки
            html_content = page.content()
            with open('debug_page.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info("HTML страницы сохранен в debug_page.html")
            
        except Exception as e:
            logger.error(f"Произошла ошибка: {e}")
        finally:
            browser.close()
            logger.info("Браузер закрыт")

if __name__ == "__main__":
    parse_addresses() 