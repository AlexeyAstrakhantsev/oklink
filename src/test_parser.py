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
            
            # Сначала настраиваем observer
            setup_observer_script = """
            () => {
                window.tooltipData = [];
                
                const observer = new MutationObserver((mutationsList) => {
                    for (const mutation of mutationsList) {
                        mutation.addedNodes.forEach(node => {
                            if (node.nodeType === 1 && node.classList.contains('okui-tooltip')) {
                                const text = node.innerText.trim();
                                const lines = text.split('\\n');
                
                                if (lines.length === 2 && /^0x[a-f0-9]{40}$/i.test(lines[1])) {
                                    window.tooltipData.push({
                                        label: lines[0],
                                        address: lines[1],
                                    });
                                    console.log('Parsed:', window.tooltipData[window.tooltipData.length - 1]);
                                } else if (/^0x[a-f0-9]{40}$/i.test(text)) {
                                    window.tooltipData.push({
                                        label: null,
                                        address: text,
                                    });
                                    console.log('Parsed:', window.tooltipData[window.tooltipData.length - 1]);
                                }
                            }
                        });
                    }
                });
                
                observer.observe(document.body, { childList: true, subtree: true });
                return true;
            }
            """
            
            # Настраиваем observer
            logger.info("Настройка observer...")
            page.evaluate(setup_observer_script)
            
            # Теперь запускаем наведение мыши
            hover_script = """
            () => {
                const addressElements = document.querySelectorAll('.index_innerClassName__6ivtc');
                console.log('Найдено элементов с адресами:', addressElements.length);
                
                let delay = 500;
                addressElements.forEach((el, i) => {
                    setTimeout(() => {
                        el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                    }, i * delay);
                });
                
                // Ждем завершения всех наведений
                return new Promise((resolve) => {
                    setTimeout(() => {
                        resolve(window.tooltipData);
                    }, (addressElements.length * delay) + 2000);
                });
            }
            """
            
            # Выполняем наведение мыши и получаем tooltips
            logger.info("Запуск наведения мыши...")
            tooltips = page.evaluate(hover_script)
            logger.info(f"Собрано tooltips: {len(tooltips)}")
            
            # Обрабатываем собранные tooltips
            for tooltip in tooltips:
                try:
                    # Сохраняем только если есть имя
                    if tooltip['label']:
                        addresses[tooltip['address']] = tooltip['label']
                        print(f"\nАдрес: {tooltip['address']}")
                        print(f"Имя: {tooltip['label']}")
                        print("-" * 50)
                    else:
                        logger.debug(f"Пропущен адрес без имени: {tooltip['address']}")
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