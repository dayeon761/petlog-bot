import datetime as dt

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import db, keyboards, texts, triage_data
from bot.config import FOLLOWUP_HOURS
from bot.states import Triage

router = Router()

STATE_BY_CATEGORY = {
    "rf": Triage.red_flags.state,
    "bh": Triage.behavior_signs.state,
    "gs": Triage.general_signs.state,
}
DATA_KEY_BY_CATEGORY = {"rf": "red_flags", "bh": "behavior_signs", "gs": "general_signs"}


def format_clinics() -> str:
    lines = [texts.CLINICS_HEADER, texts.CLINICS_PLACEHOLDER_NOTE, ""]
    for clinic in triage_data.CLINICS:
        lines.append(f"• {clinic['name']}\n  {clinic['address']}, {clinic['phone']}")
    return "\n".join(lines)


def compute_outcome(behavior_selected: set[int], general_selected: set[int]) -> tuple[str, list[str]]:
    reasons = []
    if triage_data.GENERAL_SIGN_NO_FOOD in general_selected:
        reasons.append(triage_data.GENERAL_SIGNS[triage_data.GENERAL_SIGN_NO_FOOD])
    if triage_data.GENERAL_SIGN_REPEATED_VOMIT in general_selected:
        reasons.append(triage_data.GENERAL_SIGNS[triage_data.GENERAL_SIGN_REPEATED_VOMIT])
    if len(behavior_selected) >= 2:
        reasons.append(f"{len(behavior_selected)} признака боли одновременно")
    if reasons:
        return "SEE_TODAY", reasons
    return "WAIT", []


async def begin_triage(message: Message, state: FSMContext, pet) -> None:
    await state.update_data(
        pet_id=pet["id"], species=pet["species"], pet_name=pet["name"],
        red_flags=[], behavior_signs=[], general_signs=[],
    )
    await state.set_state(Triage.red_flags)
    await message.answer(texts.TRIAGE_INTRO)
    items = triage_data.red_flags_for_species(pet["species"])
    await message.answer(
        texts.RED_FLAGS_PROMPT, reply_markup=keyboards.checklist(items, set(), "rf", "Далее ➡️")
    )


@router.message(F.text == texts.BTN_CHECK_SYMPTOMS)
async def check_symptoms(message: Message, state: FSMContext) -> None:
    pets = await db.get_pets(message.chat.id)
    if not pets:
        await message.answer(texts.NO_PETS_YET, reply_markup=keyboards.add_pet_prompt())
        return
    if len(pets) == 1:
        await begin_triage(message, state, pets[0])
        return
    await state.set_state(Triage.choose_pet)
    await message.answer("Какого питомца проверяем?", reply_markup=keyboards.choose_pet(pets))


@router.callback_query(F.data.startswith("triage_pet:"))
async def choose_pet_callback(callback: CallbackQuery, state: FSMContext) -> None:
    pet_id = int(callback.data.split(":", 1)[1])
    pet = await db.get_pet(pet_id)
    if pet is None or pet["owner_chat_id"] != callback.message.chat.id:
        await callback.answer("Питомец не найден", show_alert=True)
        return
    await callback.answer()
    await begin_triage(callback.message, state, pet)


async def finish_triage(callback: CallbackQuery, state: FSMContext, outcome: str, reasons: list[str]) -> None:
    data = await state.get_data()
    pet = await db.get_pet(data["pet_id"])
    followup_due_at = None
    if outcome == "WAIT":
        followup_due_at = (dt.datetime.now() + dt.timedelta(hours=FOLLOWUP_HOURS)).isoformat()
    await db.create_symptom_check(pet["id"], pet["owner_chat_id"], outcome, followup_due_at)
    await state.clear()
    await callback.answer()

    if outcome == "GO_NOW":
        header, body = texts.RESULT_GO_NOW_HEADER, texts.RESULT_GO_NOW_BODY
    elif outcome == "SEE_TODAY":
        header, body = texts.RESULT_SEE_TODAY_HEADER, texts.RESULT_SEE_TODAY_BODY
    else:
        header, body = texts.RESULT_WAIT_HEADER, texts.RESULT_WAIT_BODY

    parts = [header, body]
    if reasons:
        parts.append("Основание: " + "; ".join(reasons))
    if outcome in ("GO_NOW", "SEE_TODAY"):
        parts.append(format_clinics())
    if outcome == "WAIT":
        watch_items = triage_data.red_flags_for_species(pet["species"])
        parts.append(
            "Немедленно обращайтесь к врачу, если появится:\n"
            + "\n".join(f"• {item}" for item in watch_items)
        )

    await callback.message.answer("\n\n".join(parts), reply_markup=keyboards.main_menu())


@router.callback_query(F.data.startswith("chk:"))
async def checklist_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    _, category, action = callback.data.split(":", 2)
    current_state = await state.get_state()
    if current_state != STATE_BY_CATEGORY.get(category):
        await callback.answer("Этот шаг уже пройден.")
        return

    data = await state.get_data()
    species = data["species"]
    key = DATA_KEY_BY_CATEGORY[category]
    items = {
        "rf": triage_data.red_flags_for_species(species),
        "bh": triage_data.behavior_signs_for_species(species),
        "gs": triage_data.GENERAL_SIGNS,
    }[category]
    selected = set(data.get(key, []))

    if action == "next":
        if category == "rf":
            if selected:
                reasons = [items[i] for i in sorted(selected)]
                await finish_triage(callback, state, "GO_NOW", reasons)
                return
            await state.set_state(Triage.behavior_signs)
            await callback.answer()
            behavior_items = triage_data.behavior_signs_for_species(species)
            await callback.message.answer(
                texts.BEHAVIOR_SIGNS_PROMPT,
                reply_markup=keyboards.checklist(behavior_items, set(), "bh", "Далее ➡️"),
            )
            return
        if category == "bh":
            await state.set_state(Triage.general_signs)
            await callback.answer()
            await callback.message.answer(
                texts.GENERAL_SIGNS_PROMPT,
                reply_markup=keyboards.checklist(triage_data.GENERAL_SIGNS, set(), "gs", "Готово ✅"),
            )
            return
        # category == "gs"
        behavior_selected = set(data.get("behavior_signs", []))
        outcome, reasons = compute_outcome(behavior_selected, selected)
        await finish_triage(callback, state, outcome, reasons)
        return

    index = int(action)
    if index in selected:
        selected.discard(index)
    else:
        selected.add(index)
    await state.update_data(**{key: list(selected)})
    await callback.answer()
    next_label = "Готово ✅" if category == "gs" else "Далее ➡️"
    await callback.message.edit_reply_markup(reply_markup=keyboards.checklist(items, selected, category, next_label))
