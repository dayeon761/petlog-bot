import datetime as dt

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import db, keyboards, texts
from bot.config import DEWORM_INTERVAL_DAYS, VACCINATION_INTERVAL_DAYS
from bot.states import AddPet

router = Router()

SPECIES_LABELS = {"cat": "🐱 Кошка/кот", "dog": "🐶 Собака"}
FLEA_TICK_INTERVAL_LABELS = {30: "раз в месяц", 60: "раз в 2 месяца", 90: "раз в 3 месяца"}

DATE_FORMAT = "%d.%m.%Y"


def parse_date(text: str) -> dt.date:
    parsed = dt.datetime.strptime(text.strip(), DATE_FORMAT).date()
    if parsed > dt.date.today():
        raise ValueError("date in future")
    return parsed


async def start_add_pet(message_or_callback, state: FSMContext) -> None:
    await state.set_state(AddPet.name)
    target = message_or_callback.message if isinstance(message_or_callback, CallbackQuery) else message_or_callback
    await target.answer(texts.ASK_PET_NAME, reply_markup=keyboards.cancel_only())


@router.message(F.text == texts.BTN_ADD_PET)
async def add_pet_button(message: Message, state: FSMContext) -> None:
    await start_add_pet(message, state)


@router.callback_query(F.data == "go_add_pet")
async def add_pet_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await start_add_pet(callback, state)


@router.message(StateFilter(AddPet.name))
async def add_pet_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name or len(name) > 50:
        await message.answer("Введите кличку текстом, до 50 символов.")
        return
    await state.update_data(name=name)
    await state.set_state(AddPet.species)
    await message.answer(texts.ASK_PET_SPECIES, reply_markup=keyboards.species_choice())


@router.callback_query(StateFilter(AddPet.species), F.data.startswith("species:"))
async def add_pet_species(callback: CallbackQuery, state: FSMContext) -> None:
    species = callback.data.split(":", 1)[1]
    await state.update_data(species=species)
    await state.set_state(AddPet.age)
    await callback.answer()
    await callback.message.answer(texts.ASK_PET_AGE, reply_markup=keyboards.cancel_only())


@router.message(StateFilter(AddPet.age))
async def add_pet_age(message: Message, state: FSMContext) -> None:
    try:
        age = int((message.text or "").strip())
        if not (0 <= age <= 30):
            raise ValueError
    except ValueError:
        await message.answer(texts.INVALID_AGE)
        return
    await state.update_data(age=age)
    await state.set_state(AddPet.last_vaccination)
    await message.answer(texts.ASK_LAST_VACCINATION, reply_markup=keyboards.skip_date())


async def _ask_flea_tick_interval(message: Message, state: FSMContext) -> None:
    await state.set_state(AddPet.flea_tick_interval)
    await message.answer(texts.ASK_FLEA_TICK_INTERVAL, reply_markup=keyboards.flea_tick_interval_choice())


@router.message(StateFilter(AddPet.last_vaccination))
async def add_pet_last_vaccination_text(message: Message, state: FSMContext) -> None:
    try:
        last_date = parse_date(message.text or "")
    except ValueError:
        await message.answer(texts.INVALID_DATE)
        return
    next_date = last_date + dt.timedelta(days=VACCINATION_INTERVAL_DAYS)
    await state.update_data(
        last_vaccination_date=last_date.isoformat(), next_vaccination_date=next_date.isoformat()
    )
    await _ask_flea_tick_interval(message, state)


@router.callback_query(StateFilter(AddPet.last_vaccination), F.data == "skip_date")
async def add_pet_last_vaccination_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(last_vaccination_date=None, next_vaccination_date=None)
    await callback.answer()
    await _ask_flea_tick_interval(callback.message, state)


@router.callback_query(StateFilter(AddPet.flea_tick_interval), F.data.startswith("fleaint:"))
async def add_pet_flea_tick_interval(callback: CallbackQuery, state: FSMContext) -> None:
    interval_days = int(callback.data.split(":", 1)[1])
    await state.update_data(flea_tick_interval_days=interval_days)
    await state.set_state(AddPet.last_flea_tick)
    await callback.answer()
    await callback.message.answer(texts.ASK_LAST_FLEA_TICK, reply_markup=keyboards.skip_date())


async def _ask_last_deworm(message: Message, state: FSMContext) -> None:
    await state.set_state(AddPet.last_deworm)
    await message.answer(texts.ASK_LAST_DEWORM, reply_markup=keyboards.skip_date())


@router.message(StateFilter(AddPet.last_flea_tick))
async def add_pet_last_flea_tick_text(message: Message, state: FSMContext) -> None:
    try:
        last_date = parse_date(message.text or "")
    except ValueError:
        await message.answer(texts.INVALID_DATE)
        return
    data = await state.get_data()
    interval_days = data["flea_tick_interval_days"]
    next_date = last_date + dt.timedelta(days=interval_days)
    await state.update_data(
        last_flea_tick_date=last_date.isoformat(), next_flea_tick_date=next_date.isoformat()
    )
    await _ask_last_deworm(message, state)


@router.callback_query(StateFilter(AddPet.last_flea_tick), F.data == "skip_date")
async def add_pet_last_flea_tick_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(last_flea_tick_date=None, next_flea_tick_date=None)
    await callback.answer()
    await _ask_last_deworm(callback.message, state)


async def _finalize_pet(chat_id: int, state: FSMContext, message: Message) -> None:
    data = await state.get_data()
    await db.add_pet(
        owner_chat_id=chat_id,
        name=data["name"],
        species=data["species"],
        age=data["age"],
        last_vaccination_date=data.get("last_vaccination_date"),
        next_vaccination_date=data.get("next_vaccination_date"),
        flea_tick_interval_days=data["flea_tick_interval_days"],
        last_flea_tick_date=data.get("last_flea_tick_date"),
        next_flea_tick_date=data.get("next_flea_tick_date"),
        last_deworm_date=data.get("last_deworm_date"),
        next_deworm_date=data.get("next_deworm_date"),
    )
    await state.clear()
    summary = format_pet_summary(
        name=data["name"],
        species=data["species"],
        age=data["age"],
        next_vax=data.get("next_vaccination_date"),
        flea_tick_interval_days=data["flea_tick_interval_days"],
        next_flea_tick=data.get("next_flea_tick_date"),
        next_deworm=data.get("next_deworm_date"),
    )
    await message.answer(f"Питомец добавлен!\n\n{summary}", reply_markup=keyboards.main_menu())


@router.message(StateFilter(AddPet.last_deworm))
async def add_pet_last_deworm_text(message: Message, state: FSMContext) -> None:
    try:
        last_date = parse_date(message.text or "")
    except ValueError:
        await message.answer(texts.INVALID_DATE)
        return
    next_date = last_date + dt.timedelta(days=DEWORM_INTERVAL_DAYS)
    await state.update_data(
        last_deworm_date=last_date.isoformat(), next_deworm_date=next_date.isoformat()
    )
    await _finalize_pet(message.chat.id, state, message)


@router.callback_query(StateFilter(AddPet.last_deworm), F.data == "skip_date")
async def add_pet_last_deworm_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(last_deworm_date=None, next_deworm_date=None)
    await callback.answer()
    await _finalize_pet(callback.message.chat.id, state, callback.message)


def format_pet_summary(
    name: str,
    species: str,
    age: int,
    next_vax: str | None,
    flea_tick_interval_days: int,
    next_flea_tick: str | None,
    next_deworm: str | None,
) -> str:
    interval_label = FLEA_TICK_INTERVAL_LABELS.get(flea_tick_interval_days, f"раз в {flea_tick_interval_days} дней")
    lines = [
        f"Кличка: {name}",
        f"Вид: {SPECIES_LABELS.get(species, species)}",
        f"Возраст: {age}",
        f"Следующая прививка: {next_vax or 'дата неизвестна, добавьте позже'}",
        f"Следующая обработка от блох/клещей ({interval_label}): "
        f"{next_flea_tick or 'дата неизвестна, добавьте позже'}",
        f"Следующая обработка от глистов: {next_deworm or 'дата неизвестна, добавьте позже'}",
    ]
    return "\n".join(lines)


@router.message(F.text == texts.BTN_MY_PETS)
async def list_pets(message: Message) -> None:
    pets = await db.get_pets(message.chat.id)
    if not pets:
        await message.answer(texts.NO_PETS_YET, reply_markup=keyboards.add_pet_prompt())
        return
    for pet in pets:
        summary = format_pet_summary(
            name=pet["name"],
            species=pet["species"],
            age=pet["age"],
            next_vax=pet["next_vaccination_date"],
            flea_tick_interval_days=pet["flea_tick_interval_days"],
            next_flea_tick=pet["next_flea_tick_date"],
            next_deworm=pet["next_deworm_date"],
        )
        await message.answer(summary, reply_markup=keyboards.pet_actions(pet["id"]))


async def _pet_or_alert(callback: CallbackQuery, pet_id: int):
    pet = await db.get_pet(pet_id)
    if pet is None or pet["owner_chat_id"] != callback.message.chat.id:
        await callback.answer("Питомец не найден", show_alert=True)
        return None
    return pet


async def _refresh_pet_card(callback: CallbackQuery, pet_id: int) -> None:
    """Re-renders the pet's card in place after any action, so the new due dates are
    visible right where the button was — otherwise it's unclear whether a tap on
    "сделано" actually did anything, since the old card just sat there unchanged."""
    pet = await db.get_pet(pet_id)
    summary = format_pet_summary(
        name=pet["name"],
        species=pet["species"],
        age=pet["age"],
        next_vax=pet["next_vaccination_date"],
        flea_tick_interval_days=pet["flea_tick_interval_days"],
        next_flea_tick=pet["next_flea_tick_date"],
        next_deworm=pet["next_deworm_date"],
    )
    try:
        await callback.message.edit_text(summary, reply_markup=keyboards.pet_actions(pet_id))
    except TelegramBadRequest:
        pass  # marked "done" twice same day — dates didn't change, nothing to edit


@router.callback_query(F.data.startswith("petvax:"))
async def pet_vax_done(callback: CallbackQuery) -> None:
    pet_id = int(callback.data.split(":", 1)[1])
    if await _pet_or_alert(callback, pet_id) is None:
        return
    next_date = dt.date.today() + dt.timedelta(days=VACCINATION_INTERVAL_DAYS)
    await db.mark_vaccination_done(pet_id, next_date.isoformat())
    await callback.answer("Прививка отмечена ✅")
    await _refresh_pet_card(callback, pet_id)


@router.callback_query(F.data.startswith("petflea:"))
async def pet_flea_tick_done(callback: CallbackQuery) -> None:
    pet_id = int(callback.data.split(":", 1)[1])
    if await _pet_or_alert(callback, pet_id) is None:
        return
    await db.mark_flea_tick_done(pet_id)
    await callback.answer("Обработка от блох/клещей отмечена ✅")
    await _refresh_pet_card(callback, pet_id)


@router.callback_query(F.data.startswith("petdeworm:"))
async def pet_deworm_done(callback: CallbackQuery) -> None:
    pet_id = int(callback.data.split(":", 1)[1])
    if await _pet_or_alert(callback, pet_id) is None:
        return
    await db.mark_deworm_done(pet_id)
    await callback.answer("Обработка от глистов отмечена ✅")
    await _refresh_pet_card(callback, pet_id)


@router.callback_query(F.data.startswith("petdel:"))
async def pet_delete(callback: CallbackQuery) -> None:
    pet_id = int(callback.data.split(":", 1)[1])
    pet = await _pet_or_alert(callback, pet_id)
    if pet is None:
        return
    await db.delete_pet(pet_id, callback.message.chat.id)
    await callback.answer("Удалено")
    await callback.message.edit_text(f"Питомец «{pet['name']}» удалён.", reply_markup=None)
