# Dockerfile — оптимизированный под разработку
FROM python:3.12-slim

WORKDIR /app

# Устанавливаем зависимости системы
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc wget gnupg ca-certificates fonts-liberation libasound2 \
    libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcups2 libdbus-1-3 \
    libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 libwayland-client0 \
    libxcomposite1 libxdamage1 libxfixes3 libxkbcommon0 libxrandr2 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Создаём пользователя
RUN useradd -m -u 1000 botuser && \
    mkdir -p /home/botuser/.cache && \
    chown -R botuser:botuser /home/botuser /app

USER botuser

# Устанавливаем зависимости Python
COPY --chown=botuser:botuser requirements.txt .
RUN pip install --user --no-cache-dir --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# Устанавливаем Playwright браузеры под botuser
ENV PATH="/home/botuser/.local/bin:$PATH"
RUN playwright install chromium

# Настройки окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Moscow \
    PLAYWRIGHT_BROWSERS_PATH=/home/botuser/.cache/ms-playwright

CMD ["python", "-m", "main"]
