from aiogram.fsm.state import StatesGroup, State


class AddProductState(StatesGroup):
    waiting_for_url = State()
    waiting_for_size = State()


class SetDiscountState(StatesGroup):
    waiting_for_discount = State()


class SetPVZState(StatesGroup):
    waiting_for_address = State()
