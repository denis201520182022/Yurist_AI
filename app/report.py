"""Карточка лида для юриста и файл-передача с историей диалога."""
from datetime import datetime
from pathlib import Path

from app.state import SLOTS, Session

OUT_DIR = Path(__file__).resolve().parent.parent / "out"

VERDICT_LABELS = {
    "suitable": "подходит",
    "complex_suitable": "подходит (есть сложности)",
    "not_suitable": "не подходит",
    "need_more_info": "недостаточно данных",
}

END_LABELS = {
    "booked": "записан на консультацию",
    "not_suitable": "отказ (не прошёл квалификацию)",
    "handoff": "передан человеку",
    "client_declined": "клиент отказался",
    "other": "завершён",
}


def _fmt_value(key: str, value) -> str:
    if key == "debt_total" and isinstance(value, (int, float)):
        return f"{value:,.0f} ₽".replace(",", " ")
    return str(value)


def build_card(session: Session) -> str:
    """Текстовая карточка собранной информации — то, что уходит юристу."""
    lines = [
        "══════════ КАРТОЧКА КЛИЕНТА ══════════",
        f"Сессия: {session.id} | Дата: {session.created_at.strftime('%d.%m.%Y %H:%M')} | Канал: {session.channel}",
        "",
    ]
    order = [
        "name", "contact", "region", "debt_total", "creditors", "property",
        "mortgage", "collateral", "deals", "family", "income", "employment",
        "pressure", "preferred_time", "notes",
    ]
    for key in order:
        meta = SLOTS[key]
        value = session.slots.get(key)
        shown = _fmt_value(key, value) if value not in (None, "") else "— не указано"
        lines.append(f"{meta['label']}: {shown}")
    lines.append("")
    lines.append("────────── КВАЛИФИКАЦИЯ ──────────")
    if session.verdict:
        v = session.verdict
        lines.append(f"Вердикт: {VERDICT_LABELS.get(v.get('verdict'), v.get('verdict'))}")
        if v.get("reason"):
            lines.append(f"Причина: {v['reason']}")
        if v.get("complexity_flags"):
            lines.append(f"Флаги сложности: {', '.join(v['complexity_flags'])}")
        if v.get("lawyer_note"):
            lines.append(f"Заметка юристу: {v['lawyer_note']}")
    else:
        lines.append("Не проводилась")
    lines.append(f"Итог: {END_LABELS.get(session.end_result, '—')}")
    lines.append("══════════════════════════════════")
    return "\n".join(lines)


def save_transcript(session: Session, card: str) -> Path:
    """Красиво оформленная история диалога — имитация передачи клиента человеку."""
    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"transfer_{stamp}_{session.id}.md"
    lines = [
        f"# Передача диалога: клиент → юрист",
        "",
        f"- **Сессия:** `{session.id}`",
        f"- **Канал:** {session.channel}",
        f"- **Дата начала:** {session.created_at.strftime('%d.%m.%Y %H:%M')}",
        "",
        "## Карточка клиента",
        "",
        "```text",
        card,
        "```",
        "",
        "## История диалога",
        "",
    ]
    for msg in session.history:
        who = "Клиент" if msg["role"] == "user" else "Анна (агент)"
        lines.append(f"**{who}** ({msg['ts']}):")
        lines.append("")
        lines.append(msg["content"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
