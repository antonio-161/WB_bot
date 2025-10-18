#!/bin/bash

# Скрипт восстановления базы данных из бэкапа
# Использование: ./restore.sh <backup_file.sql.gz>

set -e

# Проверка аргументов
if [ $# -eq 0 ]; then
    echo "❌ Укажите файл бэкапа"
    echo "Использование: ./restore.sh <backup_file.sql.gz>"
    echo ""
    echo "Доступные бэкапы:"
    ls -lh ./backups/*.sql.gz 2>/dev/null || echo "  Нет бэкапов"
    exit 1
fi

BACKUP_FILE=$1

# Проверка существования файла
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "❌ Файл не найден: ${BACKUP_FILE}"
    exit 1
fi

# Загружаем переменные из .env
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

CONTAINER_NAME="wb_postgres"

echo "⚠️  ВНИМАНИЕ: Это удалит все текущие данные!"
echo "📁 Файл бэкапа: ${BACKUP_FILE}"
read -p "Продолжить? (yes/no): " -r REPLY
echo

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "❌ Отменено"
    exit 0
fi

# Проверяем контейнер
if ! docker ps | grep -q ${CONTAINER_NAME}; then
    echo "❌ Контейнер ${CONTAINER_NAME} не запущен!"
    exit 1
fi

echo "🔄 Останавливаю бота..."
docker-compose stop bot

echo "🔄 Восстанавливаю базу данных..."

# Распаковываем и восстанавливаем
if [[ $BACKUP_FILE == *.gz ]]; then
    gunzip -c "${BACKUP_FILE}" | docker exec -i ${CONTAINER_NAME} psql \
        -U ${POSTGRES_USER:-botuser} \
        -d ${POSTGRES_DB:-wb_bot}
else
    cat "${BACKUP_FILE}" | docker exec -i ${CONTAINER_NAME} psql \
        -U ${POSTGRES_USER:-botuser} \
        -d ${POSTGRES_DB:-wb_bot}
fi

echo "✅ База данных восстановлена!"

echo "🔄 Запускаю бота..."
docker-compose start bot

echo "✨ Готово!"