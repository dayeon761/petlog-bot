import datetime as dt

import aiosqlite

from bot.config import DEWORM_INTERVAL_DAYS, DB_PATH, FLEA_TICK_DEFAULT_INTERVAL_DAYS

SCHEMA = """
CREATE TABLE IF NOT EXISTS pets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_chat_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    species TEXT NOT NULL,
    age INTEGER NOT NULL,
    last_vaccination_date TEXT,
    next_vaccination_date TEXT,
    flea_tick_interval_days INTEGER NOT NULL DEFAULT 30,
    last_flea_tick_date TEXT,
    next_flea_tick_date TEXT,
    last_deworm_date TEXT,
    next_deworm_date TEXT,
    vax_reminder_sent_on TEXT,
    flea_tick_reminder_sent_on TEXT,
    deworm_reminder_sent_on TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS symptom_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL,
    owner_chat_id INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    created_at TEXT NOT NULL,
    followup_due_at TEXT,
    followup_sent INTEGER NOT NULL DEFAULT 0
);
"""


async def _migrate_legacy_treatment_columns(db: aiosqlite.Connection) -> None:
    """Older schema had one combined last_treatment_date/next_treatment_date pair
    for both flea/tick and deworming, on a single 90-day cycle. That's inaccurate —
    flea/tick protection is usually monthly, deworming is quarterly — so it's split
    into two pairs. Migrates any pre-existing rows instead of dropping them.
    """
    cursor = await db.execute("PRAGMA table_info(pets)")
    columns = {row[1] for row in await cursor.fetchall()}
    if "last_treatment_date" not in columns:
        return

    db.row_factory = aiosqlite.Row
    legacy_rows = await (await db.execute("SELECT * FROM pets")).fetchall()

    await db.execute("ALTER TABLE pets RENAME TO pets_legacy")
    await db.execute(
        """
        CREATE TABLE pets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_chat_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            species TEXT NOT NULL,
            age INTEGER NOT NULL,
            last_vaccination_date TEXT,
            next_vaccination_date TEXT,
            flea_tick_interval_days INTEGER NOT NULL DEFAULT 30,
            last_flea_tick_date TEXT,
            next_flea_tick_date TEXT,
            last_deworm_date TEXT,
            next_deworm_date TEXT,
            vax_reminder_sent_on TEXT,
            flea_tick_reminder_sent_on TEXT,
            deworm_reminder_sent_on TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    for row in legacy_rows:
        last_treatment = row["last_treatment_date"]
        next_flea_tick = None
        if last_treatment:
            last_date = dt.date.fromisoformat(last_treatment)
            next_flea_tick = (
                last_date + dt.timedelta(days=FLEA_TICK_DEFAULT_INTERVAL_DAYS)
            ).isoformat()
        await db.execute(
            """
            INSERT INTO pets (
                id, owner_chat_id, name, species, age,
                last_vaccination_date, next_vaccination_date,
                flea_tick_interval_days, last_flea_tick_date, next_flea_tick_date,
                last_deworm_date, next_deworm_date,
                vax_reminder_sent_on, flea_tick_reminder_sent_on, deworm_reminder_sent_on,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["owner_chat_id"],
                row["name"],
                row["species"],
                row["age"],
                row["last_vaccination_date"],
                row["next_vaccination_date"],
                FLEA_TICK_DEFAULT_INTERVAL_DAYS,
                last_treatment,
                next_flea_tick,
                last_treatment,
                row["next_treatment_date"],
                row["vax_reminder_sent_on"],
                None,
                row["treat_reminder_sent_on"],
                row["created_at"],
            ),
        )

    await db.execute("DROP TABLE pets_legacy")
    await db.commit()


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()
        await _migrate_legacy_treatment_columns(db)


def _today() -> str:
    return dt.date.today().isoformat()


async def add_pet(
    owner_chat_id: int,
    name: str,
    species: str,
    age: int,
    last_vaccination_date: str | None,
    next_vaccination_date: str | None,
    flea_tick_interval_days: int,
    last_flea_tick_date: str | None,
    next_flea_tick_date: str | None,
    last_deworm_date: str | None,
    next_deworm_date: str | None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO pets (
                owner_chat_id, name, species, age,
                last_vaccination_date, next_vaccination_date,
                flea_tick_interval_days, last_flea_tick_date, next_flea_tick_date,
                last_deworm_date, next_deworm_date,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                owner_chat_id,
                name,
                species,
                age,
                last_vaccination_date,
                next_vaccination_date,
                flea_tick_interval_days,
                last_flea_tick_date,
                next_flea_tick_date,
                last_deworm_date,
                next_deworm_date,
                dt.datetime.now().isoformat(),
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def get_pets(owner_chat_id: int) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM pets WHERE owner_chat_id = ? ORDER BY id", (owner_chat_id,)
        )
        return await cursor.fetchall()


async def get_pet(pet_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        return await cursor.fetchone()


async def delete_pet(pet_id: int, owner_chat_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM pets WHERE id = ? AND owner_chat_id = ?", (pet_id, owner_chat_id)
        )
        await db.commit()


async def mark_vaccination_done(pet_id: int, next_date: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE pets
            SET last_vaccination_date = ?, next_vaccination_date = ?, vax_reminder_sent_on = NULL
            WHERE id = ?
            """,
            (_today(), next_date, pet_id),
        )
        await db.commit()


async def mark_flea_tick_done(pet_id: int) -> str:
    pet = await get_pet(pet_id)
    interval = pet["flea_tick_interval_days"] if pet else FLEA_TICK_DEFAULT_INTERVAL_DAYS
    next_date = (dt.date.today() + dt.timedelta(days=interval)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE pets
            SET last_flea_tick_date = ?, next_flea_tick_date = ?, flea_tick_reminder_sent_on = NULL
            WHERE id = ?
            """,
            (_today(), next_date, pet_id),
        )
        await db.commit()
    return next_date


async def mark_deworm_done(pet_id: int) -> str:
    next_date = (dt.date.today() + dt.timedelta(days=DEWORM_INTERVAL_DAYS)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE pets
            SET last_deworm_date = ?, next_deworm_date = ?, deworm_reminder_sent_on = NULL
            WHERE id = ?
            """,
            (_today(), next_date, pet_id),
        )
        await db.commit()
    return next_date


async def get_due_vaccinations() -> list[aiosqlite.Row]:
    today = _today()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM pets
            WHERE next_vaccination_date IS NOT NULL
              AND next_vaccination_date <= ?
              AND (vax_reminder_sent_on IS NULL OR vax_reminder_sent_on != ?)
            """,
            (today, today),
        )
        return await cursor.fetchall()


async def get_due_flea_tick() -> list[aiosqlite.Row]:
    today = _today()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM pets
            WHERE next_flea_tick_date IS NOT NULL
              AND next_flea_tick_date <= ?
              AND (flea_tick_reminder_sent_on IS NULL OR flea_tick_reminder_sent_on != ?)
            """,
            (today, today),
        )
        return await cursor.fetchall()


async def get_due_deworm() -> list[aiosqlite.Row]:
    today = _today()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM pets
            WHERE next_deworm_date IS NOT NULL
              AND next_deworm_date <= ?
              AND (deworm_reminder_sent_on IS NULL OR deworm_reminder_sent_on != ?)
            """,
            (today, today),
        )
        return await cursor.fetchall()


async def set_vax_reminder_sent(pet_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE pets SET vax_reminder_sent_on = ? WHERE id = ?", (_today(), pet_id)
        )
        await db.commit()


async def set_flea_tick_reminder_sent(pet_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE pets SET flea_tick_reminder_sent_on = ? WHERE id = ?", (_today(), pet_id)
        )
        await db.commit()


async def set_deworm_reminder_sent(pet_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE pets SET deworm_reminder_sent_on = ? WHERE id = ?", (_today(), pet_id)
        )
        await db.commit()


async def create_symptom_check(
    pet_id: int, owner_chat_id: int, outcome: str, followup_due_at: str | None
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO symptom_checks (pet_id, owner_chat_id, outcome, created_at, followup_due_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (pet_id, owner_chat_id, outcome, dt.datetime.now().isoformat(), followup_due_at),
        )
        await db.commit()
        return cursor.lastrowid


async def get_due_followups() -> list[aiosqlite.Row]:
    now = dt.datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM symptom_checks
            WHERE followup_due_at IS NOT NULL
              AND followup_due_at <= ?
              AND followup_sent = 0
            """,
            (now,),
        )
        return await cursor.fetchall()


async def mark_followup_sent(check_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE symptom_checks SET followup_sent = 1 WHERE id = ?", (check_id,)
        )
        await db.commit()
