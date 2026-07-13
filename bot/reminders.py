import asyncio
import logging

from aiogram import Bot

from bot import db, texts
from bot.config import REMINDER_CHECK_INTERVAL_MINUTES

logger = logging.getLogger(__name__)


async def _send_vaccination_reminders(bot: Bot) -> None:
    for pet in await db.get_due_vaccinations():
        try:
            await bot.send_message(
                pet["owner_chat_id"],
                f"💉 Пора сделать прививку питомцу «{pet['name']}» "
                f"(дата: {pet['next_vaccination_date']}). Отметьте в «Мои питомцы», когда сделаете.",
            )
            await db.log_reminder_sent(pet["id"], "vaccination")
        except Exception:
            logger.exception("Failed to send vaccination reminder for pet %s", pet["id"])
        finally:
            await db.set_vax_reminder_sent(pet["id"])


async def _send_flea_tick_reminders(bot: Bot) -> None:
    for pet in await db.get_due_flea_tick():
        try:
            await bot.send_message(
                pet["owner_chat_id"],
                f"🦟 Пора обработать от блох/клещей питомца «{pet['name']}» "
                f"(дата: {pet['next_flea_tick_date']}). Отметьте в «Мои питомцы», когда сделаете.",
            )
            await db.log_reminder_sent(pet["id"], "flea_tick")
        except Exception:
            logger.exception("Failed to send flea/tick reminder for pet %s", pet["id"])
        finally:
            await db.set_flea_tick_reminder_sent(pet["id"])


async def _send_deworm_reminders(bot: Bot) -> None:
    for pet in await db.get_due_deworm():
        try:
            await bot.send_message(
                pet["owner_chat_id"],
                f"🪱 Пора обработать от глистов питомца «{pet['name']}» "
                f"(дата: {pet['next_deworm_date']}). Отметьте в «Мои питомцы», когда сделаете.",
            )
            await db.log_reminder_sent(pet["id"], "deworm")
        except Exception:
            logger.exception("Failed to send deworm reminder for pet %s", pet["id"])
        finally:
            await db.set_deworm_reminder_sent(pet["id"])


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
            await _send_vaccination_reminders(bot)
            await _send_flea_tick_reminders(bot)
            await _send_deworm_reminders(bot)
            await _send_followups(bot)
        except Exception:
            logger.exception("Reminder loop iteration failed")
        await asyncio.sleep(REMINDER_CHECK_INTERVAL_MINUTES * 60)
