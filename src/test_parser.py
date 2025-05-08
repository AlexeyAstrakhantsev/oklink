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
                                    console.log('Новый tooltip:', text);
                                }
                            }
                        });
                    }
                });
                
                observer.observe(document.body, { childList: true, subtree: true });
                
                const addressElements = document.querySelectorAll('.okui-tooltip-neutral');
                console.log('Найдено элементов с адресами:', addressElements.length);
                
                let delay = 100;
                
                return new Promise((resolve) => {
                    let processed = 0;
                    addressElements.forEach((el, i) => {
                        setTimeout(() => {
                            const event = new MouseEvent('mouseover', { bubbles: true });
                            el.dispatchEvent(event);
                            console.log('Наведение на элемент:', el.textContent.trim());
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
            
            # Обрабатываем собранные tooltips
            for tooltip in tooltips:
                try:
                    # Разбиваем текст на строки и удаляем пустые строки
                    lines = [line.strip() for line in tooltip.split('\n') if line.strip()]
                    
                    # Ищем строку с адресом (начинается с 0x)
                    address_line = next((line for line in lines if line.startswith('0x')), None)
                    if address_line:
                        # Если есть строка перед адресом и она не похожа на адрес - это имя
                        name_line = None
                        if lines.index(address_line) > 0:
                            prev_line = lines[lines.index(address_line) - 1]
                            if not prev_line.startswith('0x'):
                                name_line = prev_line
                        
                        # Сохраняем только если есть имя
                        if name_line:
                            addresses[address_line] = name_line
                            print(f"\nАдрес: {address_line}")
                            print(f"Имя: {name_line}")
                            print("-" * 50)
                        else:
                            logger.debug(f"Пропущен адрес без имени: {address_line}")
                    else:
                        logger.warning(f"Пропущен tooltip (не найден адрес): {tooltip}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке tooltip: {e}")
                    logger.error(f"Содержимое tooltip: {tooltip}")
                    continue
            
            # Выводим итоговую статистику
            print(f"\nВсего найдено уникальных адресов с именами: {len(addresses)}")
            
        except Exception as e:
            logger.error(f"Произошла ошибка: {e}")
        finally:
            browser.close()
            logger.info("Браузер закрыт")

if __name__ == "__main__":
    parse_addresses() 