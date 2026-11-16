import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
DB_PATH = os.getenv("DB_PATH", "data/requests.db").strip()

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError as exc:
    raise RuntimeError(
        "В .env необходимо указать корректный числовой ADMIN_ID"
    ) from exc

try:
    COOLDOWN_SECONDS = int(
        os.getenv("COOLDOWN_SECONDS", "600")
    )
except ValueError as exc:
    raise RuntimeError(
        "COOLDOWN_SECONDS должен быть целым числом"
    ) from exc

if not BOT_TOKEN:
    raise RuntimeError("Не указан BOT_TOKEN в файле .env")

if COOLDOWN_SECONDS < 0:
    raise RuntimeError(
        "COOLDOWN_SECONDS не может быть отрицательным"
    )