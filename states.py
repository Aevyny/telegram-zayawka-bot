from aiogram.fsm.state import State, StatesGroup


class ApplicationForm(StatesGroup):
    name = State()
    phone = State()
    comment = State()
    confirm = State()


class AdminReply(StatesGroup):
    waiting_for_text = State()