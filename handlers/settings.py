from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from states.user_states import SetDiscountState
from services.db import DB

router = Router()


@router.message(Command("setdiscount"))
async def cmd_setdiscount(message: Message, state: FSMContext):
    """Запрос скидки."""
    await message.answer(
        "Установите скидку WB кошелька в процентах (целое число 0–100). "
        "Например: 7"
    )
    await state.set_state(SetDiscountState.waiting_for_discount)


@router.message(SetDiscountState.waiting_for_discount)
async def process_discount(message: Message, state: FSMContext, db: DB):
    """Установка скидки."""
    try:
        v = int(message.text.strip())
        if v < 0 or v > 100:
            raise ValueError
    except ValueError:
        await message.answer("Введите целое число от 0 до 100.")
        return
    await db.ensure_user(message.from_user.id)
    await db.set_discount(message.from_user.id, v)
    await message.answer(f"Скидка установлена: {v}% (учту при показе цены).")
    await state.clear()
