# script1/Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.41.0

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY requirements.txt .
COPY src/ ./src/

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаем директорию для результатов
RUN mkdir -p /app/results

# Запускаем скрипт
CMD ["python", "src/test_parser.py"]