# script1/Dockerfile
FROM python:3.11-slim

# Установка необходимых системных зависимостей
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем только requirements.txt
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем Playwright и его зависимости
RUN playwright install chromium
RUN playwright install-deps

# Создаем точку монтирования для кода
VOLUME ["/app/src"]

# Создаем директорию для результатов
RUN mkdir -p /app/results

# Запускаем скрипт
CMD ["python", "src/gpt_parser.py"]