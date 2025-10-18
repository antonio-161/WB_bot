#!/bin/bash

# Скрипт резервного копирования базы данных
# Использование: ./backup.sh [backup_name]

set -e

# Загружаем переменные из .env
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Параметры
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME=${1:-"backup_${TIMESTAMP}"}
BACKUP_FILE="${BACKUP_DIR}/${BACKUP_NAME}.sql"
CONTAINER_NAME="wb_postgres"

# Создаём директорию если не существует
mkdir -p "${BACKUP_DIR}"

echo "🔄 Начинаю резервное копирование..."
echo "📦 Контейнер: ${CONTAINER_NAME}"
echo "💾 Файл: ${BACKUP_FILE}"

# Проверяем что контейнер запущен
if ! docker ps | grep -q ${CONTAINER_NAME}; then
    echo "❌ Контейнер ${CONTAINER_NAME} не запущен!"
    exit 1
fi

# Создаём backup
docker exec -t ${CONTAINER_NAME} pg_dump \
    -U ${POSTGRES_USER:-botuser} \
    -d ${POSTGRES_DB:-wb_bot} \
    --clean \
    --if-exists \
    > "${BACKUP_FILE}"

# Сжимаем
gzip "${BACKUP_FILE}"
BACKUP_FILE="${BACKUP_FILE}.gz"

# Получаем размер
SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)

echo "✅ Резервная копия создана успешно!"
echo "📁 Файл: ${BACKUP_FILE}"
echo "📊 Размер: ${SIZE}"

# Удаляем старые бэкапы (старше 30 дней)
echo "🧹 Удаляю старые бэкапы (>30 дней)..."
find "${BACKUP_DIR}" -name "backup_*.sql.gz" -mtime +30 -delete

echo "✨ Готово!"