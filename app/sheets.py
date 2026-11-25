"""Интеграция с Google Таблицами для автоматической выгрузки лидов."""
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Заголовки столбцов таблицы
HEADERS = [
    "Дата и время",
    "ID сессии",
    "Имя клиента",
    "Телефон / Контакт",
    "Сумма долга, ₽",
    "Кредиторы",
    "Регион прописки",
    "Имущество",
    "Сделки (3 года)",
    "Семья / Дети",
    "Занятость / Доход",
    "Приставы / Коллекторы",
    "Удобное время встречи",
    "Статус квалификации",
    "Итог обращения",
    "Заметка юристу",
]

_client = None
_worksheet = None


def _get_worksheet():
    global _client, _worksheet
    if _worksheet is not None:
        return _worksheet

    creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "hhhrzabota-1c66f9f87769.json")
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "1V4rFCAtBA_8cngtwT7sB3WhIqSsHyCUX45ptg7Sp_sA")

    path = Path(creds_file)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path

    if not path.exists():
        logger.warning("Файл сервисного аккаунта Google не найден: %s", path)
        return None

    try:
        import gspread

        _client = gspread.service_account(filename=str(path))
        sh = _client.open_by_key(sheet_id)
        ws = sh.sheet1

        # Проверяем и создаём шапку таблицы при первом запуске
        existing = ws.row_values(1)
        if not existing:
            ws.append_row(HEADERS)
            logger.info("В Google Таблицу добавлена шапка столбцов")

        _worksheet = ws
        return _worksheet
    except Exception as e:  # noqa: BLE001
        logger.warning("Не удалось подключиться к Google Таблице: %s", e)
        return None


def export_lead(session) -> bool:
    """Выгружает лида в Google Таблицу одной новой строкой."""
    ws = _get_worksheet()
    if ws is None:
        return False

    slots = session.slots
    verdict = session.verdict or {}

    debt = slots.get("debt_total", "")
    if isinstance(debt, (int, float)):
        debt_str = f"{debt:,.0f}".replace(",", " ")
    else:
        debt_str = str(debt) if debt else "—"

    row = [
        datetime.now().strftime("%d.%m.%Y %H:%M"),
        session.id,
        slots.get("name", "—"),
        slots.get("contact", "—"),
        debt_str,
        slots.get("creditors", "—"),
        slots.get("region", "—"),
        slots.get("property", "—"),
        slots.get("deals", "—"),
        slots.get("family", "—"),
        slots.get("income", "—"),
        slots.get("pressure", "—"),
        slots.get("preferred_time", "—"),
        verdict.get("verdict", "—"),
        session.end_result or "—",
        verdict.get("lawyer_note", "—"),
    ]

    try:
        ws.append_row(row)
        logger.info("📊 Лид #%s успешно выгружен в Google Таблицу", session.id)
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("Ошибка при добавлении строки в Google Таблицу: %s", e)
        return False
