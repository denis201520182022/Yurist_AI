"""Карточка лида для юриста и файл-передача с историей диалога."""
from datetime import datetime
from pathlib import Path

from app.state import SLOTS, Session

OUT_DIR = Path(__file__).resolve().parent.parent / "out"

VERDICT_BADGES = {
    "suitable": "✅ Подходит под процедуру",
    "complex_suitable": "⚠️ Подходит (есть нюансы)",
    "not_suitable": "❌ Не подходит",
    "need_more_info": "ℹ️ Требуется уточнение данных",
}

END_BADGES = {
    "booked": " Записан на консультацию",
    "not_suitable": " Отказ (не подходит под критерии)",
    "handoff": " Передан живому юристу",
    "client_declined": " Клиент отказался от записи",
    "other": " Диалог завершён",
}


def _fmt_value(key: str, value) -> str:
    if key == "debt_total" and isinstance(value, (int, float)):
        return f"{value:,.0f} ₽".replace(",", " ")
    return str(value)


def build_card(session: Session) -> str:
    """Красивая, структурированная карточка для Telegram-сообщения."""
    v = session.verdict or {}
    verdict_text = VERDICT_BADGES.get(v.get("verdict"), v.get("verdict", "Не проводилась"))
    status_text = END_BADGES.get(session.end_result, "—")

    name = session.slots.get("name", "Не указано")
    contact = session.slots.get("contact", "Не указан")
    time_pref = session.slots.get("preferred_time", "Уточнить у клиента")
    region = session.slots.get("region", "Не указан")
    debt = _fmt_value("debt_total", session.slots.get("debt_total", "Не указана"))
    creditors = session.slots.get("creditors", "—")

    # Собираем только заполненные дополнительные данные, чтобы не спамить пустыми строками
    extra_items = []
    details_map = [
        ("property", " Имущество"),
        ("mortgage", " Ипотека"),
        ("collateral", " Залоги"),
        ("deals", " Сделки (3 года)"),
        ("family", " Семья / Дети"),
        ("income", " Доход / Расходы"),
        ("employment", " Занятость"),
        ("pressure", " Приставы / Коллекторы"),
        ("notes", " Примечания"),
    ]
    for slot_key, label in details_map:
        val = session.slots.get(slot_key)
        if val not in (None, "", "— не указано", "null"):
            extra_items.append(f"• {label}: {val}")

    extra_block = "\n".join(extra_items) if extra_items else "• Существенных обременений и имущества не заявлено"

    # Формируем итоговую карточку
    card = f"""📋 <b>КАРТОЧКА КЛИЕНТА ДЛЯ ЮРИСТА</b>
<i>Сессия: #{session.id} | {session.created_at.strftime('%d.%m.%Y %H:%M')}</i>

👤 <b>Контактные данные:</b>
• Клиент: <b>{name}</b>
• Связь: <code>{contact}</code>
• Регион прописки: <b>{region}</b>
• Удобное время: <b>{time_pref}</b>

💰 <b>Финансовая ситуация:</b>
• Сумма долга: <b>{debt}</b>
• Кредиторы: {creditors}

📂 <b>Детали и активы:</b>
{extra_block}

⚖️ <b>Квалификация лида:</b>
• Статус: <b>{verdict_text}</b>
• Итог: <b>{status_text}</b>"""

    if v.get("reason"):
        card += f"\n• Обоснование: <i>{v['reason']}</i>"
    if v.get("complexity_flags"):
        card += f"\n• Флаги сложности: <code>{', '.join(v['complexity_flags'])}</code>"
    if v.get("lawyer_note"):
        card += f"\n\n💡 <b>Рекомендация юристу:</b>\n{v['lawyer_note']}"

    return card.strip()


def build_transcript_content(session: Session, card: str) -> str:
    """Красиво оформленный Markdown передачи диалога без сохранения на диск."""
    v = session.verdict or {}
    verdict_text = VERDICT_BADGES.get(v.get("verdict"), v.get("verdict", "Не проводилась"))
    status_text = END_BADGES.get(session.end_result, "—")

    md = [
        f"#  Карточка передачи клиента: {session.slots.get('name', 'Клиент')} (#{session.id})",
        "",
        f"> **Дата обращения:** {session.created_at.strftime('%d.%m.%Y %H:%M')}  ",
        f"> **Канал обращения:** {session.channel}  ",
        f"> **Статус записи:** {status_text}  ",
        f"> **Вердикт квалификации:** {verdict_text}  ",
        "",
        "---",
        "",
        "##  Сводка по клиенту",
        "",
        "| Параметр | Значение |",
        "| :--- | :--- |",
        f"| **Имя** | {session.slots.get('name', '—')} |",
        f"| **Контакт** | `{session.slots.get('contact', '—')}` |",
        f"| **Регион прописки** | {session.slots.get('region', '—')} |",
        f"| **Сумма долга** | **{_fmt_value('debt_total', session.slots.get('debt_total', '—'))}** |",
        f"| **Кредиторы** | {session.slots.get('creditors', '—')} |",
        f"| **Желаемое время** | {session.slots.get('preferred_time', '—')} |",
        "",
        "### Дополнительные сведения о ситуации",
        "",
    ]

    details_map = [
        ("property", "Имущество"),
        ("mortgage", "Ипотека"),
        ("collateral", "Залоги"),
        ("deals", "Сделки за 3 года"),
        ("family", "Семья и дети"),
        ("income", "Доход и расходы"),
        ("employment", "Занятость (работа/ИП/бизнес)"),
        ("pressure", "Приставы, суды, коллекторы"),
        ("notes", "Заметки"),
    ]
    has_details = False
    for slot_key, label in details_map:
        val = session.slots.get(slot_key)
        if val not in (None, "", "— не указано", "null"):
            md.append(f"- **{label}:** {val}")
            has_details = True
    if not has_details:
        md.append("_Клиент не сообщил о наличии спорного имущества, ипотек или исполнительных производств._")

    md.extend([
        "",
        "### Рекомендации юристу на консультацию",
        "",
        f"- **Причина квалификации:** {v.get('reason', 'Стандартный случай')}",
    ])
    if v.get("complexity_flags"):
        md.append(f"- **Флаги сложности:** `{', '.join(v['complexity_flags'])}`")
    if v.get("lawyer_note"):
        md.append(f"- **Что проверить:** {v['lawyer_note']}")

    md.extend([
        "",
        "---",
        "",
        "## 💬 Полная стенограмма диалога",
        "",
    ])

    for msg in session.history:
        who = "👤 Клиент" if msg["role"] == "user" else "👩‍💼 Анна (консультант)"
        md.append(f"#### {who} `[{msg.get('ts', '')}]`")
        md.append(msg["content"])
        md.append("")

    return "\n".join(md)
