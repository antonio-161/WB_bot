from aiogram.fsm.state import StatesGroup, State


class AddProductState(StatesGroup):
    waiting_for_url = State()


class SetDiscountState(StatesGroup):
    waiting_for_discount = State()
