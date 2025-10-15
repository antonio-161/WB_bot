from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from services.db import DB
from keyboards.kb import choose_plan_kb, main_inline_kb

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, db: DB):
    """Приветствие, учёт пользователя и выбор тарифа при первом запуске."""
    user = await db.ensure_user(message.from_user.id)

    # Если пользователь новый (ещё не выбрал тариф)
    if not user.get("plan"):
        await message.answer(
            text=(
                "🔮 <b>Добро пожаловать в мир цен и скидок!</b>\n\n"
                "Я — ваш Telegram-бот для отслеживания цен на Wildberries.\n\n"
                "✨ Что я умею:\n"
                "⚡ Уведомлять о снижении цен\n"
                "📈 Показывать динамику стоимости\n"
                "📊 Экспортировать данные для анализа\n\n"
                "🎁 <b>Первые 5 товаров</b> вы можете отслеживать бесплатно.\n\n"
                "Выберите тариф, чтобы начать 👇"
            ),
            reply_markup=choose_plan_kb(),
            parse_mode="HTML",
        )

    # Если у пользователя уже есть тариф →
    # просто приветствуем и показываем меню
    else:
        plan = user.get("plan_name", "Ваш тариф не определён 🤔")
        await message.answer(
            text=(
                f"👋 С возвращением, <b>{message.from_user.first_name}</b>!\n\n"
                f"📦 Ваш текущий тариф: <b>{plan}</b>\n"
                "Продолжайте отслеживать товары или добавьте новые 👇"
            ),
            reply_markup=main_inline_kb(),
            parse_mode="HTML",
        )
