from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


# Главное меню пользователя

start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="📝 Оставить заявку"
            )
        ]
    ],
    resize_keyboard=True,
    input_field_placeholder="Нажмите, чтобы оставить заявку"
)


# Подтверждение заявки

confirm_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data="application:confirm"
            ),
            InlineKeyboardButton(
                text="✏️ Заполнить заново",
                callback_data="application:restart"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data="application:cancel"
            )
        ]
    ]
)


# Клавиатура администратора

def admin_request_keyboard(request_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✉️ Ответить пользователю",
                    callback_data=f"admin:reply:{request_id}"
                )
            ]
        ]
    )