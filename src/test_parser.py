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
                
                // Ищем все элементы с адресами
                const addressElements = document.querySelectorAll('a[href^="/ethereum/address/"]');
                console.log('Найдено элементов с адресами:', addressElements.length);
                
                let delay = 500;
                
                return new Promise((resolve) => {
                    let processed = 0;
                    addressElements.forEach((el, i) => {
                        setTimeout(() => {
                            const event = new MouseEvent('mouseover', { bubbles: true });
                            el.dispatchEvent(event);
                            processed++;
                            if (processed === addressElements.length) {
                                setTimeout(() => resolve(tooltips), 2000);
                            }
                        }, i * delay);
                    });
                });
            }
            """
            
            # Выполняем скрипт и получаем tooltips
            logger.info("Запуск сбора tooltips...")
            tooltips = page.evaluate(tooltips_script)
            logger.info(f"Собрано tooltips: {len(tooltips)}")
            
            # Сохраняем HTML страницы для отладки
            html_content = page.content()
            with open('debug_page.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info("HTML страницы сохранен в debug_page.html")
            
            # Обрабатываем собранные tooltips
            for tooltip in tooltips:
                try:
                    # Разбиваем текст на строки и удаляем пустые строки
                    lines = [line.strip() for line in tooltip.split('\n') if line.strip()]
                    
                    # Проверяем, что у нас есть как минимум две строки
                    if len(lines) >= 2:
                        # Проверяем, что вторая строка похожа на адрес (начинается с 0x)
                        if lines[1].startswith('0x'):
                            name = lines[0]
                            address = lines[1]
                            addresses[address] = name
                            print(f"\nАдрес: {address}")
                            print(f"Имя: {name}")
                            print("-" * 50)
                        else:
                            logger.warning(f"Пропущен tooltip (неверный формат адреса): {tooltip}")
                    else:
                        logger.warning(f"Пропущен tooltip (недостаточно строк): {tooltip}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке tooltip: {e}")
                    logger.error(f"Содержимое tooltip: {tooltip}")
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