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

# Получаем настройки из переменных окружения
blockchain = os.getenv('BLOCKCHAIN', 'ethereum')
url = f"https://www.oklink.com/{blockchain}/tx-list"

def is_valid_address(address: str, chain: str) -> bool:
    """Проверка валидности адреса в зависимости от блокчейна"""
    if chain.lower() == 'tron':
        # Tron адреса в сокращенном виде: начинаются с T и содержат ...
        return address.startswith('T') and '...' in address
    else:
        # EVM адреса в сокращенном виде: начинаются с 0x и содержат ...
        return address.startswith('0x') and '...' in address

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
        page = None  # Будем пересоздавать страницу при необходимости
        
        while True:  # Бесконечный цикл
            try:
                logger.info("🔄 Начинаем новую итерацию сбора данных")
                
                # Создаем новую страницу, если нужно
                if page is None or page.is_closed():
                    logger.info("🌟 Создаем новую страницу браузера")
                    page = await browser.new_page()
                    
                # Устанавливаем таймаут для операций
                page.set_default_timeout(30000)  # 30 секунд на операции (вместо 60)
                    
                # Переходим на страницу с таймаутом
                await page.goto(url, wait_until='networkidle', timeout=30000)
                logger.info("✅ Страница загружена успешно")
                
                # Дополнительная пауза для полной загрузки
                await page.wait_for_timeout(1000)  # 1 секунда для полной загрузки

                # Инициализируем список результатов
                parsed_results = []
                tooltips = set()  # Множество для уникальных tooltips

                # Поиск всех иконок риска на странице
                risk_icons = await page.query_selector_all(".oklink-explore-danger")
                logger.info(f"🔍 Найдено иконок риска на странице: {len(risk_icons)}")
                
                # Сначала наводим на все иконки
                for i, risk_icon in enumerate(risk_icons):
                    try:
                        logger.info(f"ℹ️ Наведение на иконку риска #{i+1}")
                        await risk_icon.hover()
                        await page.wait_for_timeout(300)
                    except Exception as e:
                        logger.error(f"❌ Ошибка при наведении на иконку #{i+1}: {e}")

                # Теперь собираем все тултипы
                risk_tooltips = await page.query_selector_all(".okui-popup-layer-content.index_conWrapper__PSJYS")
                logger.info(f"🔍 Найдено тултипов риска: {len(risk_tooltips)}")
                
                for i, tooltip in enumerate(risk_tooltips):
                    try:
                        risk_text = await tooltip.inner_text()
                        logger.info(f"🔴 Тултип риска #{i+1}: {risk_text}")
                        
                        # Извлекаем имя из текста после "reported as"
                        if "reported as" in risk_text:
                            # Получаем имя и убираем слово "address" в конце
                            name = risk_text.split("reported as")[1].strip()
                            if name.endswith(" address"):
                                name = name[:-8]  # убираем " address" в конце
                            
                            # Получаем адрес из того же блока
                            address_element = await page.query_selector(f".index_wrapper__ns7tB:nth-child({i+1}) .index_address__7NLO9")
                            if address_element:
                                logger.info(f"🔍 Найден элемент адреса #{i+1}")
                                # Получаем адрес из href
                                href = await address_element.get_attribute("href")
                                if href:
                                    # Извлекаем адрес из href (формат: /tron/address/TVmowKrNepsDeEwzvtMr1cfg1eJE5G2ux9)
                                    address = href.split('/')[-1]
                                    logger.info(f"📝 Найден адрес для риска: {address}")
                                    
                                    # Добавляем в parsed_results
                                    parsed_results.append({
                                        "type": name,  # Используем имя как тип
                                        "name": name,  # И как имя
                                        "address": address
                                    })
                                    logger.info(f"✅ Добавлен риск: {name} для адреса {address}")
                                else:
                                    logger.error(f"❌ Не найден href для элемента {i+1}")
                                    continue
                        
                        tooltips.add(risk_text)
                    except Exception as e:
                        logger.error(f"❌ Ошибка при получении текста тултипа #{i+1}: {e}")

                # Продолжаем с основным циклом
                for attempt in range(1, attempts + 1):
                    logger.info(f"🔁 Попытка {attempt} из {attempts}")
                    try:
                        address_elements = await page.query_selector_all(".index_wrapper__ns7tB")
                        logger.info(f"🔍 Найдено {len(address_elements)} адресов")

                        for i in range(len(address_elements)):
                            try:
                                fresh_elements = await page.query_selector_all(".index_wrapper__ns7tB")
                                if i >= len(fresh_elements):
                                    continue

                                element = fresh_elements[i]
                                
                                # Сначала проверяем наличие иконки риска
                                risk_icon = await element.query_selector(".index_riskIcon__u0+KY")
                                if not risk_icon:
                                    # Если не нашли внутри элемента, ищем в родительском блоке
                                    parent = await element.evaluate('el => el.closest(".index_wrapper__ns7tB")')
                                    if parent:
                                        # Создаем новый элемент из родительского
                                        parent_element = await page.query_selector(f".index_wrapper__ns7tB:nth-child({i+1})")
                                        if parent_element:
                                            risk_icon = await parent_element.query_selector(".index_riskIcon__u0+KY")
                                
                                if risk_icon:
                                    logger.info("⚠️ Найдена иконка риска")
                                    await risk_icon.hover()
                                    await page.wait_for_timeout(300)
                                    
                                    # Ждем появления тултипа риска
                                    try:
                                        risk_tooltip = await page.wait_for_selector(".okui-popup-layer-content.index_conWrapper__PSJYS", timeout=1000)
                                        if risk_tooltip:
                                            risk_text = await risk_tooltip.inner_text()
                                            logger.info(f"🔴 Тултип риска: {risk_text}")
                                            # Используем текст риска как имя
                                            tooltips.add(risk_text)
                                            continue
                                    except Exception as e:
                                        logger.error(f"❌ Ошибка при получении тултипа риска: {e}")
                                else:
                                    logger.debug("ℹ️ Иконка риска не найдена")
                                
                                # Если иконки риска нет, проверяем содержимое элемента
                                text = await element.inner_text()
                                text = text.strip()
                                
                                # Проверяем, является ли текст адресом для текущего блокчейна
                                if is_valid_address(text, blockchain):
                                    logger.debug(f"⏩ Пропускаем элемент только с адресом: {text}")
                                    continue

                                # Если есть дополнительный текст (имя) - делаем наведение
                                logger.info(f"🔄 Наведение на элемент с именем: {text}")
                                await element.hover()
                                await page.wait_for_timeout(300)

                                # Получаем основной тултип
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
                        
                        try:
                            await page.reload(wait_until='networkidle', timeout=30000)
                            await page.wait_for_timeout(2000)  # 2 секунды вместо 3
                        except Exception as reload_error:
                            logger.error(f"⚠️ Ошибка при перезагрузке страницы: {reload_error}")
                            # Создаем новую страницу, так как текущая может быть сломана
                            await page.close()
                            page = await browser.new_page()
                            await page.goto(url, wait_until='networkidle', timeout=30000)

                # Обработка и сохранение tooltip'ов
                for tooltip in tooltips:
                    # Для Tron формат: "Type: Name\nAddress"
                    if blockchain.lower() == 'tron':
                        lines = tooltip.split('\n')
                        if len(lines) == 2:
                            type_name = lines[0].split(': ', 1)
                            if len(type_name) == 2:
                                result = {
                                    "type": type_name[0],
                                    "name": type_name[1],
                                    "address": lines[1].strip()
                                }
                                parsed_results.append(result)
                    else:
                        # Для EVM формат: "Type: Name 0x..." или просто "Name 0x..."
                        match = re.match(r"(?:(?P<type>\w+):\s+)?(?P<name>.+?)\s+(?P<address>0x[a-fA-F0-9]{40})", tooltip)
                        if match:
                            result = {
                                "type": match.group("type") or "other",  # если тип не найден, используем "other"
                                "name": match.group("name"),
                                "address": match.group("address")
                            }
                            parsed_results.append(result)

                logger.info(f"\n🔎 Распознано адресов с именами: {len(parsed_results)}")
                for item in parsed_results:
                    logger.info(f"🔹 Type: {item['type']}, Name: {item['name']}, Address: {item['address']}")
                    # Сохраняем в базу данных
                    try:
                        address_data = {
                            'address': item['address'],
                            'name': item['name'],
                            'tag': item['type'],
                            'chain': blockchain
                        }
                        address_repo.save_address(address_data)
                        logger.info(f"✅ Сохранен адрес: {item['address']} с именем: {item['name']} и тегом: {item['type']}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка при сохранении адреса {item['address']}: {e}")

                # Пауза между итерациями (1 секунда)
                logger.info("💤 Пауза 1 секунда перед следующей итерацией...")
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"❌ Критическая ошибка в основном цикле: {e}")
                
                # Пытаемся закрыть страницу, если она еще существует
                try:
                    if page and not page.is_closed():
                        await page.close()
                except:
                    pass
                    
                # Сбрасываем страницу, чтобы создать новую в следующей итерации
                page = None
                
                logger.info("💤 Пауза 10 секунд перед повторной попыткой...")
                await asyncio.sleep(10)
                
                # Проверяем, не закрылся ли браузер
                try:
                    # Если браузер закрылся, создаем новый
                    if browser.is_connected() == False:
                        logger.info("🔄 Браузер отключен, запускаем новый")
                        browser = await p.chromium.launch(headless=True)
                except Exception as browser_error:
                    logger.error(f"⚠️ Ошибка при проверке браузера: {browser_error}")
                    browser = await p.chromium.launch(headless=True)

# Запуск скрипта
if __name__ == "__main__":
    while True:
        try:
            asyncio.run(scrape_tooltips(url, attempts=3))
        except Exception as e:
            logger.critical(f"🔥 Критическая ошибка вне основного цикла: {e}")
            logger.info("💤 Перезапуск скрипта через 30 секунд...")
            time.sleep(30)
