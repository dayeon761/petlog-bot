from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import db, keyboards, texts

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await db.upsert_user(message.chat.id)
    await message.answer(texts.WELCOME, reply_markup=keyboards.main_menu())


@router.message(Command("help"))
@router.message(F.text == texts.BTN_HELP)
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP, reply_markup=keyboards.main_menu())


async def _do_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=keyboards.main_menu())


@router.message(StateFilter("*"), Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await _do_cancel(message, state)


@router.message(StateFilter("*"), F.text == texts.BTN_CANCEL)
async def btn_cancel(message: Message, state: FSMContext) -> None:
    await _do_cancel(message, state)
