import asyncio
import logging

from aiogram import Bot

from bot import db, texts
from bot.config import REMINDER_CHECK_INTERVAL_MINUTES

logger = logging.getLogger(__name__)

# Каждый трек: эмодзи + формулировка действия + функции для стадии "в срок/просрочено"
# (используют отдельный *_reminder_sent_on флаг, чтобы не слать повторно в тот же день,
# но повторять на следующий, если не отметили "сделано").
REMINDER_KINDS = {
    "vaccination": {
        "emoji": "💉",
        "label": "сделать прививку",
        "get_due": db.get_due_vaccinations,
        "set_due_sent": db.set_vax_reminder_sent,
    },
    "flea_tick": {
        "emoji": "🦟",
        "label": "обработать от блох/клещей",
        "get_due": db.get_due_flea_tick,
        "set_due_sent": db.set_flea_tick_reminder_sent,
    },
    "deworm": {
        "emoji": "🪱",
        "label": "обработать от глистов",
        "get_due": db.get_due_deworm,
        "set_due_sent": db.set_deworm_reminder_sent,
    },
}


async def _send_upcoming_reminders(bot: Bot, kind: str, days_before: int) -> None:
    info = REMINDER_KINDS[kind]
    date_field = db.REMINDER_DATE_FIELDS[kind]
    log_type = f"{kind}_{days_before}d"
    when = "Через 7 дней" if days_before == 7 else "Завтра"

    for pet in await db.get_upcoming(kind, days_before):
        if await db.has_reminder_logged_today(pet["id"], log_type):
            continue
        try:
            await bot.send_message(
                pet["owner_chat_id"],
                f"{info['emoji']} {when} пора {info['label']} питомцу «{pet['name']}» "
                f"(дата: {pet[date_field]}).",
            )
            await db.log_reminder_sent(pet["id"], log_type)
        except Exception:
            logger.exception("Failed to send %s reminder for pet %s", log_type, pet["id"])


async def _send_due_reminders(bot: Bot, kind: str) -> None:
    info = REMINDER_KINDS[kind]
    date_field = db.REMINDER_DATE_FIELDS[kind]

    for pet in await info["get_due"]():
        try:
            await bot.send_message(
                pet["owner_chat_id"],
                f"{info['emoji']} Пора {info['label']} питомцу «{pet['name']}» "
                f"(дата: {pet[date_field]}). Отметьте в «Мои питомцы», когда сделаете.",
            )
            await db.log_reminder_sent(pet["id"], kind)
        except Exception:
            logger.exception("Failed to send %s reminder for pet %s", kind, pet["id"])
        finally:
            await info["set_due_sent"](pet["id"])


async def _send_followups(bot: Bot) -> None:
    for check in await db.get_due_followups():
        pet = await db.get_pet(check["pet_id"])
        name = pet["name"] if pet else "питомца"
        try:
            await bot.send_message(check["owner_chat_id"], texts.FOLLOWUP_QUESTION.format(name=name))
            await db.log_reminder_sent(check["pet_id"], "followup")
        except Exception:
            logger.exception("Failed to send followup for check %s", check["id"])
        finally:
            await db.mark_followup_sent(check["id"])


async def reminder_loop(bot: Bot) -> None:
    while True:
        try:
            for kind in REMINDER_KINDS:
                await _send_upcoming_reminders(bot, kind, 7)
                await _send_upcoming_reminders(bot, kind, 1)
                await _send_due_reminders(bot, kind)
            await _send_followups(bot)
        except Exception:
            logger.exception("Reminder loop iteration failed")
        await asyncio.sleep(REMINDER_CHECK_INTERVAL_MINUTES * 60)
