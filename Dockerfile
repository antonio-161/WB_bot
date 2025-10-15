# Базовый образ с Python 3.12
FROM python:3.12-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем проект
COPY . .

# Указываем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Moscow

# Точка входа (по умолчанию запускаем бота)
CMD ["python", "-m", "main"]
