"""Ручная рассылка всем пользователям бота. Не бот-команда — запускается вручную
с сервера/ноутбука администратором, чтобы отправка не была доступна кому попало.

Использование:
    python -m bot.broadcast "Текст сообщения"
"""

import asyncio
import sys

from aiogram import Bot

from bot import db
from bot.config import BOT_TOKEN


async def main() -> None:
    if len(sys.argv) < 2:
        print('Использование: python -m bot.broadcast "текст сообщения"')
        return
    text = sys.argv[1]

    chat_ids = await db.get_all_user_chat_ids()
    print(f"Получателей: {len(chat_ids)}")
    print("Текст сообщения:")
    print(text)
    print()
    confirm = input(f"Отправить {len(chat_ids)} пользователям? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Отменено.")
        return

    bot = Bot(token=BOT_TOKEN)
    sent, failed = 0, 0
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, text)
            sent += 1
        except Exception as exc:
            failed += 1
            print(f"Не удалось отправить {chat_id}: {exc}")
        await asyncio.sleep(0.05)
    await bot.session.close()
    print(f"Готово. Отправлено: {sent}, ошибок: {failed}")


if __name__ == "__main__":
    asyncio.run(main())
