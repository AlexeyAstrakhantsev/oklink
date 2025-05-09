# script1/Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY requirements.txt .
COPY src/ src/
COPY .env .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаем директорию для результатов
RUN mkdir -p /app/results

# Запускаем скрипт
CMD ["python", "src/gpt_parser.py"]