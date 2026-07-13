import asyncio

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import db, keyboards, texts
from bot.config import ADMIN_CHAT_IDS
from bot.states import Broadcast

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


@router.message(Command("stats"))
async def stats_command(message: Message) -> None:
    if message.chat.id not in ADMIN_CHAT_IDS:
        await message.answer(texts.STATS_NOT_ADMIN)
        return
    stats = await db.get_stats()
    outcomes = "\n".join(f"  {k}: {v}" for k, v in stats["outcomes"].items()) or "  пока нет данных"

    last_broadcast = stats["last_broadcast"]
    if last_broadcast is None:
        broadcast_line = "  рассылок ещё не было"
    else:
        broadcast_line = (
            f"  отправлена: {last_broadcast['sent_at'][:16].replace('T', ' ')}, "
            f"получателей: {last_broadcast['recipient_count']}\n"
            f"  заходили в бота после неё: {last_broadcast['active_since']}"
        )

    await message.answer(
        texts.STATS_TEMPLATE.format(
            users=stats["users"],
            pets=stats["pets"],
            purchase_interest=stats["purchase_interest"],
            outcomes=outcomes,
            reminders_sent=_format_counts(stats["reminders_sent"]),
            currently_overdue=_format_counts(stats["currently_overdue"]),
            active_24h=stats["active_24h"],
            active_7d=stats["active_7d"],
            last_broadcast=broadcast_line,
        )
    )


@router.message(Command("broadcast"))
async def broadcast_command(message: Message, command: CommandObject, state: FSMContext) -> None:
    if message.chat.id not in ADMIN_CHAT_IDS:
        await message.answer(texts.STATS_NOT_ADMIN)
        return
    text = command.args
    if not text:
        await message.answer(texts.BROADCAST_USAGE)
        return
    chat_ids = await db.get_all_user_chat_ids()
    await state.update_data(broadcast_text=text, broadcast_chat_ids=chat_ids)
    await state.set_state(Broadcast.confirm)
    await message.answer(
        texts.BROADCAST_PREVIEW.format(count=len(chat_ids), text=text),
        reply_markup=keyboards.broadcast_confirm(),
    )


@router.callback_query(StateFilter(Broadcast.confirm), F.data == "broadcast_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer(texts.BROADCAST_CANCELLED)


@router.callback_query(StateFilter(Broadcast.confirm), F.data == "broadcast_send")
async def broadcast_send(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    text = data["broadcast_text"]
    chat_ids = data["broadcast_chat_ids"]
    await state.clear()
    await callback.answer("Отправляю...")

    sent, failed = 0, 0
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await db.log_broadcast(text, sent)
    await callback.message.answer(texts.BROADCAST_DONE.format(sent=sent, failed=failed))
