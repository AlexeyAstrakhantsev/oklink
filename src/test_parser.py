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
            
            # Внедряем JavaScript для сбора tooltips
            tooltips_script = """
            () => {
                const tooltips = [];
                
                const observer = new MutationObserver((mutationsList) => {
                    for (const mutation of mutationsList) {
                        mutation.addedNodes.forEach(node => {
                            if (node.nodeType === 1 && node.classList.contains('okui-tooltip')) {
                                const text = node.innerText.trim();
                                if (!tooltips.includes(text)) {
                                    tooltips.push(text);
                                }
                            }
                        });
                    }
                });
                
                observer.observe(document.body, { childList: true, subtree: true });
                
                const addressElements = document.querySelectorAll('.okui-tooltip-neutral');
                let delay = 100; // уменьшаем задержку
                
                // Функция для эмуляции наведения мыши
                function hoverElement(element) {
                    const event = new MouseEvent('mouseover', { bubbles: true });
                    element.dispatchEvent(event);
                }
                
                // Обрабатываем элементы с интервалом
                let index = 0;
                const interval = setInterval(() => {
                    if (index < addressElements.length) {
                        hoverElement(addressElements[index]);
                        index++;
                    } else {
                        clearInterval(interval);
                        // Возвращаем собранные tooltips через 2 секунды
                        setTimeout(() => {
                            window.tooltips = tooltips;
                        }, 2000);
                    }
                }, delay);
                
                return true;
            }
            """
            
            # Выполняем скрипт
            logger.info("Запуск сбора tooltips...")
            page.evaluate(tooltips_script)
            
            # Ждем 5 секунд для сбора tooltips
            time.sleep(5)
            
            # Получаем собранные tooltips
            tooltips = page.evaluate("() => window.tooltips || []")
            logger.info(f"Собрано tooltips: {len(tooltips)}")
            
            # Обрабатываем собранные tooltips
            for tooltip in tooltips:
                try:
                    # Разбиваем текст на строки
                    lines = tooltip.strip().split('\n')
                    if len(lines) >= 2:
                        name = lines[0].strip()
                        address = lines[1].strip()
                        if address and name:
                            addresses[address] = name
                            print(f"\nАдрес: {address}")
                            print(f"Имя: {name}")
                            print("-" * 50)
                except Exception as e:
                    logger.error(f"Ошибка при обработке tooltip: {e}")
                    continue
            
            # Выводим итоговую статистику
            print(f"\nВсего найдено уникальных адресов: {len(addresses)}")
            
        except Exception as e:
            logger.error(f"Произошла ошибка: {e}")
        finally:
            browser.close()
            logger.info("Браузер закрыт")

if __name__ == "__main__":
    parse_addresses() 