from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot import db, keyboards, texts
from bot.config import ADMIN_CHAT_IDS

router = Router()

REMINDER_TYPE_LABELS = {
    "vaccination": "прививка",
    "flea_tick": "блохи/клещи",
    "deworm": "глисты",
    "followup": "чек-ап через 12ч",
}


def _format_counts(counts: dict) -> str:
    if not counts:
        return "  пока нет данных"
    return "\n".join(f"  {REMINDER_TYPE_LABELS.get(k, k)}: {v}" for k, v in counts.items())


@router.message(F.text == texts.BTN_BUY)
async def buy_button(message: Message) -> None:
    await message.answer(texts.BUY_OFFER, reply_markup=keyboards.buy_confirm())


@router.callback_query(F.data == "buy_interest_confirm")
async def buy_confirm_callback(callback: CallbackQuery) -> None:
    is_new = await db.record_purchase_interest(callback.message.chat.id)
    await callback.answer()
    text = texts.BUY_THANKS_NEW if is_new else texts.BUY_THANKS_ALREADY
    await callback.message.answer(text, reply_markup=keyboards.main_menu())


@router.message(Command("stats"))
async def stats_command(message: Message) -> None:
    if message.chat.id not in ADMIN_CHAT_IDS:
        await message.answer(texts.STATS_NOT_ADMIN)
        return
    stats = await db.get_stats()
    outcomes = "\n".join(f"  {k}: {v}" for k, v in stats["outcomes"].items()) or "  пока нет данных"
    await message.answer(
        texts.STATS_TEMPLATE.format(
            users=stats["users"],
            pets=stats["pets"],
            purchase_interest=stats["purchase_interest"],
            outcomes=outcomes,
            reminders_sent=_format_counts(stats["reminders_sent"]),
            currently_overdue=_format_counts(stats["currently_overdue"]),
        )
    )
