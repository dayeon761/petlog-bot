import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", "bot.db")

# Chat ID пользователей, которым доступна команда /stats. Узнать свой chat_id можно
# у @userinfobot в Telegram. Несколько ID — через запятую.
ADMIN_CHAT_IDS = {int(x) for x in os.getenv("ADMIN_CHAT_IDS", "").split(",") if x.strip()}

# Как часто фоновый процесс проверяет напоминания (прививки/обработки/чек-апы)
REMINDER_CHECK_INTERVAL_MINUTES = int(os.getenv("REMINDER_CHECK_INTERVAL_MINUTES", "15"))

VACCINATION_INTERVAL_DAYS = 365

# Обработка от глистов — интервал одинаковый почти всегда, фиксируем.
DEWORM_INTERVAL_DAYS = 90

# Обработка от блох/клещей сильно зависит от конкретного препарата (капли/таблетки —
# обычно 1 месяц, есть варианты на 2-3 месяца), поэтому даём выбор при регистрации
# питомца вместо одного фиксированного интервала.
FLEA_TICK_INTERVAL_OPTIONS_DAYS = (30, 60, 90)
FLEA_TICK_DEFAULT_INTERVAL_DAYS = 30

FOLLOWUP_HOURS = 12
