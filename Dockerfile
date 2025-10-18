# ==== Stage 1: Build environment ====
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ==== Stage 2: Final runtime image ====
FROM python:3.12-slim

WORKDIR /app

# Ставим зависимости Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libatspi2.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 \
    libgtk-3-0 libnspr4 libnss3 libwayland-client0 libxcomposite1 \
    libxdamage1 libxfixes3 libxkbcommon0 libxrandr2 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Копируем окружение и код
COPY --from=builder /opt/venv /opt/venv
COPY . .

# Настраиваем окружение
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Moscow \
    PLAYWRIGHT_BROWSERS_PATH=/home/botuser/.cache/ms-playwright

# ⬇️ Устанавливаем браузеры Playwright под root
RUN playwright install chromium

# Создаём пользователя после установки браузеров
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app

USER botuser

# Healthcheck (опционально)
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import asyncio; from services.db import DB; from config import settings; asyncio.run(DB(str(settings.DATABASE_DSN)).connect())" || exit 1

CMD ["python", "-m", "main"]
