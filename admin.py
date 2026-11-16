import html
import logging

from aiogram import F, Bot, Router
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADMIN_ID
from database import (
    get_recent_requests,
    get_request_by_id,
    mark_request_answered
)
from states import AdminReply


router = Router(name="admin")

logger = logging.getLogger(__name__)


STATUS_LABELS = {
    "new": "Новая",
    "answered": "Есть ответ"
}


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ==============================
# СПИСОК ПОСЛЕДНИХ ЗАЯВОК
# ==============================

@router.message(Command("requests"))
async def show_recent_requests(message: Message):

    if not is_admin(message.from_user.id):
        return

    try:
        requests = await get_recent_requests(limit=10)

    except Exception:
        logger.exception(
            "Не удалось загрузить список заявок"
        )

        await message.answer(
            "Не удалось получить список заявок. Попробуйте позже."
        )
        return

    if not requests:
        await message.answer(
            "Пока заявок нет."
        )
        return

    blocks = []

    for item in requests:

        username = (
            f"@{item['username']}"
            if item["username"]
            else "не указан"
        )

        status = STATUS_LABELS.get(
            item["status"],
            item["status"]
        )

        comment = item["comment"]

        if len(comment) > 160:
            comment = comment[:157] + "..."

        blocks.append(
            f"<b>№{item['id']} — "
            f"{html.escape(item['name'])}</b>\n"
            f"Телефон: {html.escape(item['phone'])}\n"
            f"Комментарий: {html.escape(comment)}\n"
            f"Username: {html.escape(username)}\n"
            f"User ID: <code>{item['user_id']}</code>\n"
            f"Дата: {html.escape(item['created_at'])}\n"
            f"Статус: {html.escape(status)}"
        )

    # Разбиваем список на части, чтобы не превысить
    # максимальную длину сообщения Telegram.

    current_text = "<b>Последние заявки:</b>\n\n"

    for block in blocks:

        if len(current_text) + len(block) + 2 > 3500:

            await message.answer(current_text)

            current_text = (
                "<b>Последние заявки (продолжение):</b>\n\n"
            )

        current_text += block + "\n\n"

    if current_text.strip():
        await message.answer(current_text)


# ==============================
# НАЧАЛО ОТВЕТА
# ==============================

@router.callback_query(
    F.data.startswith("admin:reply:")
)
async def start_admin_reply(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "У вас нет доступа.",
            show_alert=True
        )
        return

    try:
        request_id = int(
            callback.data.rsplit(":", 1)[1]
        )

    except (ValueError, AttributeError):
        await callback.answer(
            "Некорректный номер заявки.",
            show_alert=True
        )
        return

    request = await get_request_by_id(request_id)

    if request is None:
        await callback.answer(
            "Заявка не найдена.",
            show_alert=True
        )
        return

    await state.clear()

    await state.set_state(
        AdminReply.waiting_for_text
    )

    await state.update_data(
        request_id=request_id
    )

    await callback.answer()

    if callback.message:
        await callback.message.answer(
            f"Напишите ответ для пользователя "
            f"по заявке №{request_id}.\n"
            "Для отмены используйте /cancel."
        )


# ==============================
# ОТПРАВКА ОТВЕТА
# ==============================

@router.message(AdminReply.waiting_for_text)
async def send_admin_reply(
    message: Message,
    state: FSMContext,
    bot: Bot
):

    if not is_admin(message.from_user.id):
        await state.clear()
        return

    answer_text = (message.text or "").strip()

    if not answer_text:
        await message.answer(
            "Отправьте ответ обычным текстовым сообщением."
        )
        return

    data = await state.get_data()

    request_id = data.get("request_id")

    request = await get_request_by_id(request_id)

    if request is None:
        await state.clear()

        await message.answer(
            "Заявка не найдена. Ответ отменён."
        )
        return

    try:

        await bot.send_message(
            chat_id=request["user_id"],
            text=(
                f"💬 <b>Ответ администратора "
                f"по заявке №{request_id}:</b>\n\n"
                f"{html.escape(answer_text)}"
            )
        )

        await mark_request_answered(request_id)

    except TelegramForbiddenError:

        await state.clear()

        await message.answer(
            "Не удалось отправить ответ: пользователь "
            "заблокировал бота или не может получать "
            "от него сообщения."
        )
        return

    except TelegramAPIError:

        logger.exception(
            "Не удалось отправить ответ по заявке №%s",
            request_id
        )

        await message.answer(
            "Telegram не принял сообщение. Попробуйте ещё раз."
        )
        return

    except Exception:

        logger.exception(
            "Ошибка при обработке ответа по заявке №%s",
            request_id
        )

        await message.answer(
            "Произошла ошибка при отправке ответа."
        )
        return

    await state.clear()

    await message.answer(
        f"✅ Ответ по заявке №{request_id} отправлен пользователю."
    )