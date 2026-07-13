from aiogram.fsm.state import State, StatesGroup


class AddPet(StatesGroup):
    name = State()
    species = State()
    age = State()
    last_vaccination = State()
    flea_tick_interval = State()
    last_flea_tick = State()
    last_deworm = State()


class Triage(StatesGroup):
    choose_pet = State()
    red_flags = State()
    behavior_signs = State()
    general_signs = State()


class Broadcast(StatesGroup):
    confirm = State()
