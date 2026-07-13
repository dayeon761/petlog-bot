from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import texts
from bot.config import FLEA_TICK_INTERVAL_OPTIONS_DAYS


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_ADD_PET), KeyboardButton(text=texts.BTN_MY_PETS)],
            [KeyboardButton(text=texts.BTN_CHECK_SYMPTOMS)],
            [KeyboardButton(text=texts.BTN_BUY)],
            [KeyboardButton(text=texts.BTN_HELP)],
        ],
        resize_keyboard=True,
    )


def cancel_only() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.BTN_CANCEL)]], resize_keyboard=True
    )


def species_choice() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🐱 Кошка/кот", callback_data="species:cat")
    builder.button(text="🐶 Собака", callback_data="species:dog")
    builder.adjust(2)
    return builder.as_markup()


def skip_date() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.BTN_SKIP, callback_data="skip_date")
    return builder.as_markup()


def flea_tick_interval_choice() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    labels = {30: "Раз в месяц", 60: "Раз в 2 месяца", 90: "Раз в 3 месяца"}
    for days in FLEA_TICK_INTERVAL_OPTIONS_DAYS:
        builder.button(text=labels.get(days, f"Раз в {days} дней"), callback_data=f"fleaint:{days}")
    builder.adjust(1)
    return builder.as_markup()


def pet_actions(pet_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Прививка сделана", callback_data=f"petvax:{pet_id}")
    builder.button(text="✅ От блох/клещей сделано", callback_data=f"petflea:{pet_id}")
    builder.button(text="✅ От глистов сделано", callback_data=f"petdeworm:{pet_id}")
    builder.button(text="🗑 Удалить", callback_data=f"petdel:{pet_id}")
    builder.adjust(1)
    return builder.as_markup()


def choose_pet(pets) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for pet in pets:
        builder.button(text=pet["name"], callback_data=f"triage_pet:{pet['id']}")
    builder.adjust(1)
    return builder.as_markup()


def add_pet_prompt() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.BTN_ADD_PET, callback_data="go_add_pet")
    return builder.as_markup()


def checklist(items: list[str], selected: set[int], category: str, next_text: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, item in enumerate(items):
        mark = "☑️" if index in selected else "⬜"
        builder.row(
            InlineKeyboardButton(text=f"{mark} {item}", callback_data=f"chk:{category}:{index}")
        )
    builder.row(InlineKeyboardButton(text=next_text, callback_data=f"chk:{category}:next"))
    return builder.as_markup()


def buy_confirm() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.BUY_CONFIRM_BTN, callback_data="buy_interest_confirm")
    return builder.as_markup()
