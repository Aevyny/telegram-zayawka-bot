import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import admin_router, user_router


async def main():

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        )
    )

    # Инициализируем базу данных.

    await init_db()

    logging.info("База данных инициализирована")

    # Создаём бота.

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    # Создаём Dispatcher с FSM.

    dp = Dispatcher(
        storage=MemoryStorage()
    )

    # Подключаем обработчики.

    dp.include_router(user_router)
    dp.include_router(admin_router)

    try:

        logging.info("Бот запущен")

        await dp.start_polling(bot)

    finally:

        await bot.session.close()

        logging.info("Сессия бота закрыта")


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")