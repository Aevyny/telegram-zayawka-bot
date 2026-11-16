import html
import logging
import re

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADMIN_ID, COOLDOWN_SECONDS
from database import create_request_if_allowed
from keyboards import (
    confirm_keyboard,
    start_keyboard,
    admin_request_keyboard
)
from states import ApplicationForm


router = Router(name="user")

logger = logging.getLogger(__name__)


# ==============================
# START
# ==============================

@router.message(CommandStart())
async def command_start(
    message: Message,
    state: FSMContext
):
    await state.clear()

    await message.answer(
        "Здравствуйте! 👋\n\n"
        "Здесь можно оставить заявку. Нажмите кнопку ниже, "
        "и я задам вам несколько вопросов.",
        reply_markup=start_keyboard
    )


# ==============================
# CANCEL
# ==============================

@router.message(Command("cancel"))
async def cancel_form(
    message: Message,
    state: FSMContext
):
    await state.clear()

    await message.answer(
        "Текущий процесс отменён. "
        "Чтобы начать заново, нажмите кнопку ниже.",
        reply_markup=start_keyboard
    )


# ==============================
# НАЧАЛО АНКЕТЫ
# ==============================

@router.message(F.text == "📝 Оставить заявку")
async def start_form(
    message: Message,
    state: FSMContext
):
    await state.clear()

    await state.set_state(ApplicationForm.name)

    await message.answer(
        "Как вас зовут?"
    )


# ==============================
# ИМЯ
# ==============================

@router.message(ApplicationForm.name)
async def process_name(
    message: Message,
    state: FSMContext
):
    name = (message.text or "").strip()

    if not 2 <= len(name) <= 80:
        await message.answer(
            "Введите имя длиной от 2 до 80 символов."
        )
        return

    await state.update_data(name=name)

    await state.set_state(ApplicationForm.phone)

    await message.answer(
        "Укажите номер телефона.\n"
        "Например: +7 999 123-45-67"
    )


# ==============================
# ТЕЛЕФОН
# ==============================

@router.message(ApplicationForm.phone)
async def process_phone(
    message: Message,
    state: FSMContext
):
    phone = (message.text or "").strip()

    digits = re.sub(r"\D", "", phone)

    if not 7 <= len(digits) <= 15:
        await message.answer(
            "Не получилось распознать номер.\n"
            "Введите номер телефона с кодом страны, "
            "например +7 999 123-45-67."
        )
        return

    await state.update_data(phone=phone)

    await state.set_state(ApplicationForm.comment)

    await message.answer(
        "Напишите, что именно вам нужно.\n"
        "Можно подробно — до 1000 символов."
    )


# ==============================
# КОММЕНТАРИЙ
# ==============================

@router.message(ApplicationForm.comment)
async def process_comment(
    message: Message,
    state: FSMContext
):
    comment = (message.text or "").strip()

    if not 3 <= len(comment) <= 1000:
        await message.answer(
            "Комментарий должен содержать от 3 до 1000 символов."
        )
        return

    await state.update_data(comment=comment)

    data = await state.get_data()

    await state.set_state(ApplicationForm.confirm)

    summary = (
        "<b>Проверьте вашу заявку:</b>\n\n"
        f"<b>Имя:</b> {html.escape(data['name'])}\n"
        f"<b>Телефон:</b> {html.escape(data['phone'])}\n"
        f"<b>Комментарий:</b>\n"
        f"{html.escape(data['comment'])}\n\n"
        "Всё верно? Подтвердите отправку."
    )

    await message.answer(
        summary,
        reply_markup=confirm_keyboard
    )


# ==============================
# ПОДТВЕРЖДЕНИЕ ЗАЯВКИ
# ==============================

@router.callback_query(
    F.data == "application:confirm",
    ApplicationForm.confirm
)
async def confirm_application(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot
):
    data = await state.get_data()

    user = callback.from_user

    # Сохраняем заявку с проверкой ограничения по времени.

    try:
        request_id, remaining = await create_request_if_allowed(
            user_id=user.id,
            username=user.username,
            name=data["name"],
            phone=data["phone"],
            comment=data["comment"],
            cooldown_seconds=COOLDOWN_SECONDS
        )

    except Exception:
        logger.exception(
            "Не удалось сохранить заявку пользователя %s",
            user.id
        )

        await callback.answer(
            "Не удалось сохранить заявку. Попробуйте позже.",
            show_alert=True
        )
        return

    # Проверяем ограничение на отправку заявок.

    if request_id is None:
        minutes = remaining // 60
        seconds = remaining % 60

        await state.clear()

        await callback.answer()

        if callback.message:
            await callback.message.edit_reply_markup(
                reply_markup=None
            )

            await callback.message.answer(
                "Вы недавно уже отправляли заявку. "
                f"Повторить отправку можно через "
                f"{minutes} мин. {seconds} сек.",
                reply_markup=start_keyboard
            )

        return

    # Формируем сообщение администратору.

    username = (
        f"@{user.username}"
        if user.username
        else "не указан"
    )

    admin_text = (
        f"🆕 <b>Новая заявка №{request_id}</b>\n\n"
        f"<b>Имя:</b> {html.escape(data['name'])}\n"
        f"<b>Телефон:</b> {html.escape(data['phone'])}\n"
        f"<b>Комментарий:</b>\n"
        f"{html.escape(data['comment'])}\n\n"
        f"<b>Username:</b> {html.escape(username)}\n"
        f"<b>ID пользователя:</b> <code>{user.id}</code>"
    )

    # Отправляем заявку администратору.

    admin_notified = True

    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            reply_markup=admin_request_keyboard(request_id)
        )

    except TelegramAPIError:
        admin_notified = False

        logger.exception(
            "Заявка №%s сохранена, но уведомление админу не отправлено",
            request_id
        )

    await state.clear()

    await callback.answer("Заявка сохранена!")

    # Сообщаем пользователю результат.

    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )

        if admin_notified:
            await callback.message.answer(
                f"✅ Ваша заявка №{request_id} принята!\n"
                "Спасибо. Администратор свяжется с вами.",
                reply_markup=start_keyboard
            )

        else:
            await callback.message.answer(
                f"✅ Заявка №{request_id} сохранена в базе.\n"
                "Но уведомление администратору не удалось доставить. "
                "Пожалуйста, попробуйте связаться с ним другим способом.",
                reply_markup=start_keyboard
            )


# ==============================
# ЗАПОЛНИТЬ ЗАНОВО
# ==============================

@router.callback_query(
    F.data == "application:restart",
    ApplicationForm.confirm
)
async def restart_application(
    callback: CallbackQuery,
    state: FSMContext
):
    await state.clear()

    await state.set_state(ApplicationForm.name)

    await callback.answer()

    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )

        await callback.message.answer(
            "Хорошо, начнём заново. Как вас зовут?"
        )


# ==============================
# ОТМЕНА АНКЕТЫ
# ==============================

@router.callback_query(
    F.data == "application:cancel",
    ApplicationForm.confirm
)
async def cancel_application_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    await state.clear()

    await callback.answer("Анкета отменена.")

    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )

        await callback.message.answer(
            "Заявка не отправлена.",
            reply_markup=start_keyboard
        )