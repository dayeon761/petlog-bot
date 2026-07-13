from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Update

from bot import db


class TrackUserMiddleware(BaseMiddleware):
    """Records every chat that interacts with the bot in any way (not just /start) —
    a single missed /start after a redeploy shouldn't make a real user invisible
    in /stats, so this is the single source of truth instead of a per-handler call.
    """

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        chat_id = None
        if event.message:
            chat_id = event.message.chat.id
        elif event.callback_query and event.callback_query.message:
            chat_id = event.callback_query.message.chat.id

        if chat_id is not None:
            await db.upsert_user(chat_id)

        return await handler(event, data)
