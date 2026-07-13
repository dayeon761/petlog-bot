from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot import db, keyboards, texts

router = Router()


@router.message(F.text == texts.BTN_BUY)
async def buy_button(message: Message) -> None:
    await message.answer(texts.BUY_OFFER, reply_markup=keyboards.buy_confirm())


@router.callback_query(F.data == "buy_interest_confirm")
async def buy_confirm_callback(callback: CallbackQuery) -> None:
    is_new = await db.record_purchase_interest(callback.message.chat.id)
    await callback.answer()
    text = texts.BUY_THANKS_NEW if is_new else texts.BUY_THANKS_ALREADY
    await callback.message.answer(text, reply_markup=keyboards.main_menu())
