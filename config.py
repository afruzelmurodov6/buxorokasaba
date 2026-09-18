import os

from dotenv import load_dotenv # type: ignore

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "0")
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL")

DB_PATH = "bot_database.db"

if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN topilmadi! .env faylini yarating va BOT_TOKEN ni kiriting "
        "(.env.example faylidan nusxa oling)."
    )

if not REQUIRED_CHANNEL:
    raise ValueError(
        "REQUIRED_CHANNEL topilmadi! .env faylida REQUIRED_CHANNEL ni kiriting "
        "(masalan: @mening_kanalim)."
    )

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except (TypeError, ValueError):
    raise ValueError("ADMIN_ID .env faylida butun son (raqam) bo'lishi kerak.")